use strict;
use warnings FATAL => 'all';
use PostgreSQL::Test::Cluster;
use PostgreSQL::Test::Utils;
use Test::More;

my $node = PostgreSQL::Test::Cluster->new('post_adaptation');
$node->init;
$node->append_conf('postgresql.conf', qq{
max_prepared_transactions = 10
autovacuum = off
wal_consistency_checking = all
});
$node->start;
my $library = $ENV{XID64_TODO_LIB};
$node->safe_psql('postgres', qq{
 CREATE FUNCTION todo_apply_lock(xid,int,bool) RETURNS void
 AS '$library' LANGUAGE C STRICT;
 CREATE FUNCTION todo_apply_try(xid,int,oid) RETURNS bool
 AS '$library' LANGUAGE C STRICT;
 CREATE FUNCTION todo_toast_xmax(regclass) RETURNS int
 AS '$library' LANGUAGE C STRICT;
 CREATE FUNCTION todo_conversion_helper_checks(regclass) RETURNS int
 AS '$library' LANGUAGE C STRICT;
});
my $a = $node->background_psql('postgres');
my $b = $node->background_psql('postgres');
$a->query_safe("SELECT todo_apply_lock('100',0,true)");
is($node->safe_psql('postgres', "SELECT todo_apply_try('4294967396',0,700001)"),
 't', 'high-half difference does not cause false contention');
$b->query_safe("SELECT todo_apply_lock('4294967396',0,true)");
is($node->safe_psql('postgres', q{
 SELECT string_agg(transactionid::text,',' ORDER BY transactionid::text::numeric)
 FROM pg_locks WHERE locktype='applytransaction' AND granted
}), '100,4294967396', 'pg_locks retains both full remote XIDs');
for my $xid ('100','4294967396')
{
 is($node->safe_psql('postgres', "SELECT todo_apply_try('$xid',0,700001)"),
  'f', "identical full key $xid conflicts");
}
is($node->safe_psql('postgres', "SELECT todo_apply_try('4294967396',1,700001)"),
 't', 'stream and transaction subtypes remain distinct');
is($node->safe_psql('postgres', "SELECT todo_apply_try('4294967396',0,700002)"),
 't', 'subscription IDs remain distinct');
my $waiter = $node->background_psql('postgres');
$waiter->query_until(qr/waiter_started/, qq{\\echo waiter_started
SELECT todo_apply_lock('4294967396',0,true);
});
ok($node->poll_query_until('postgres', q{
 SELECT count(*)=1 FROM pg_locks WHERE locktype='applytransaction'
 AND transactionid='4294967396'::xid AND NOT granted
}), 'same full-XID acquisition actually waits in the backend');
$a->query_safe("SELECT todo_apply_lock('100',0,false)");
is($node->safe_psql('postgres', q{
 SELECT count(*) FROM pg_locks WHERE locktype='applytransaction'
 AND transactionid='4294967396'::xid AND NOT granted
}), '1', 'releasing low-half peer does not release the high-XID waiter');
$b->query_safe("SELECT todo_apply_lock('4294967396',0,false)");
$waiter->query_safe("SELECT todo_apply_lock('4294967396',0,false)");
is($node->safe_psql('postgres', q{
 SELECT count(*) FROM pg_locks WHERE locktype='applytransaction'
}), '0', 'waiter completes and all apply locks are released');
$waiter->quit;
$a->quit;
$b->quit;

# Exercise both prepared-transaction outcomes with real MultiXact members.
$node->safe_psql('postgres', 'CREATE TABLE prepared_rows(n int PRIMARY KEY); INSERT INTO prepared_rows VALUES(1)');
is($node->safe_psql('postgres', "SELECT todo_conversion_helper_checks('prepared_rows')"),
 '3', 'actual regression helper handles live/redirect/unused, legacy and full double-xmax pages');
for my $case (['commit',2], ['rollback',3])
{
 my ($action,$row) = @$case;
 $a = $node->background_psql('postgres');
 $b = $node->background_psql('postgres');
 $a->query_safe("BEGIN; SELECT * FROM prepared_rows WHERE n=1 FOR KEY SHARE; INSERT INTO prepared_rows VALUES($row)");
 $b->query_safe('BEGIN; SELECT * FROM prepared_rows WHERE n=1 FOR KEY SHARE');
 is($node->safe_psql('postgres', q{
  SELECT count(*) FROM prepared_rows t,
  LATERAL pg_get_multixact_members(t.xmax) m WHERE t.n=1
 }), '2', "$action fixture has two actual MultiXact members");
 $a->query_safe("PREPARE TRANSACTION 'todo_$action'");
 $b->query_safe('COMMIT');
 $a->quit; $b->quit;
 $node->stop('immediate');
 $node->start;
 is($node->safe_psql('postgres', "SELECT count(*) FROM pg_prepared_xacts WHERE gid='todo_$action'"),
  '1', "$action prepared transaction survives crash restart");
 $node->safe_psql('postgres', uc($action) . " PREPARED 'todo_$action'");
 is($node->safe_psql('postgres', "SELECT count(*) FROM prepared_rows WHERE n=$row"),
  $action eq 'commit' ? '1' : '0', "$action prepared transaction has the expected data outcome");
 is($node->safe_psql('postgres', 'SELECT count(*) FROM pg_prepared_xacts'),
  '0', "$action removes recovered prepared state");
}

$node->safe_psql('postgres', q{
 CREATE TABLE toast_rows(n int PRIMARY KEY, body text);
 ALTER TABLE toast_rows ALTER COLUMN body SET STORAGE EXTERNAL;
 INSERT INTO toast_rows SELECT 1,string_agg(md5(g::text),'') FROM generate_series(1,2000) g;
});
my $original = $node->safe_psql('postgres','SELECT md5(body) FROM toast_rows');
$a = $node->background_psql('postgres');
$a->query_safe('BEGIN ISOLATION LEVEL REPEATABLE READ; SELECT md5(body) FROM toast_rows');
for my $round (1 .. 5)
{
 $node->safe_psql('postgres', "UPDATE toast_rows SET body=(SELECT string_agg(md5((g+$round)::text),'') FROM generate_series(1,2000) g)");
 $node->safe_psql('postgres','VACUUM toast_rows');
 is($a->query_safe('SELECT md5(body) FROM toast_rows'), $original,
  "old snapshot retains the original TOAST value during update/vacuum $round");
 is($node->safe_psql('postgres', 'SELECT todo_toast_xmax(\'toast_rows\') > 0'),
  't', "raw xmax accessor handles live TOAST pages after round $round");
}
$a->query_safe('COMMIT');
$a->quit;
$node->safe_psql('postgres','VACUUM (FREEZE) toast_rows; CHECKPOINT');
my $current = $node->safe_psql('postgres','SELECT md5(body) FROM toast_rows');
isnt($current, $original, 'new snapshot sees the updated TOAST value');
$node->stop('immediate');
$node->start;
is($node->safe_psql('postgres','SELECT md5(body) FROM toast_rows'),
 $current, 'updated TOAST value survives crash restart');
$node->stop;
done_testing();
