# Pause conversion after header publication, before line pointers/body copy.
use strict;
use warnings FATAL => 'all';
use Time::HiRes qw(sleep);
use PostgreSQL::Test::Cluster;
use PostgreSQL::Test::Utils;
use Test::More;

my $dir = $ENV{XID64_GATE_DIR};
my $library = $ENV{XID64_GATE_LIB};
my $injection_library = $ENV{XID64_GATE_INJECTION_LIB};
my $old = PostgreSQL::Test::Cluster->new('gate_old', install_path => $ENV{oldinstall});
$old->init(force_initdb => 1, xid32 => 1);
$old->append_conf('postgresql.conf', 'autovacuum = off');
$old->start;
$old->safe_psql('postgres', 'CREATE TABLE gate_table(n int); INSERT INTO gate_table VALUES(42)');
$old->safe_psql('postgres', 'VACUUM FREEZE gate_table');
$old->safe_psql('postgres', q{
	CREATE TABLE gate_no_metadata AS SELECT 7 AS n;
	CREATE TABLE gate_overwrite AS SELECT 8 AS n;
	CREATE TABLE gate_forward(n int, payload text);
	ALTER TABLE gate_forward ALTER COLUMN payload SET STORAGE PLAIN;
	INSERT INTO gate_forward VALUES(1,repeat('a',5000)),(2,repeat('b',5000));
});
for my $table ('gate_no_metadata', 'gate_overwrite', 'gate_forward')
{
	$old->safe_psql('postgres', "VACUUM FREEZE $table");
}
$old->stop;

my $node = PostgreSQL::Test::Cluster->new('gate_new');
$node->init(extra => ['--no-data-checksums']);
$node->append_conf('postgresql.conf', q{
autovacuum = off
autovacuum_freeze_max_age = 1000000000000
autovacuum_multixact_freeze_max_age = 1000000000000
io_method = worker
});
$node->command_ok([
	$node->installed_command('pg_upgrade'), '--no-sync', '--copy',
	'--old-datadir' => $old->data_dir, '--new-datadir' => $node->data_dir,
	'--old-bindir' => $old->config_data('--bindir'),
	'--new-bindir' => $node->config_data('--bindir'),
	'--socketdir' => $node->host, '--old-port' => $old->port,
	'--new-port' => $node->port], 'upgrade a real legacy page');
$node->start;
$node->safe_psql('postgres', qq{
	CREATE FUNCTION gate_attach(text,text) RETURNS void AS '$library' LANGUAGE C STRICT;
	CREATE FUNCTION gate_read(regclass,text) RETURNS int AS '$library' LANGUAGE C STRICT;
	CREATE FUNCTION gate_recent(regclass,int) RETURNS bool AS '$library' LANGUAGE C STRICT;
	CREATE FUNCTION gate_raw(regclass,int,int DEFAULT 0) RETURNS int AS '$library' LANGUAGE C STRICT;
});
for my $try (1 .. 2)
{
	my ($ret, $out, $err) = $node->psql('postgres', "SELECT gate_raw('gate_no_metadata',0)");
	is($ret, 3, "metadata-free legacy read fails normally, attempt $try");
	like($err, qr/without heap conversion metadata/, 'legacy contents are not returned to the caller');
}
is($node->safe_psql('postgres', 'TABLE gate_no_metadata'), '7',
	'normal relation read can retry the unchanged legacy page');
is($node->safe_psql('postgres', "SELECT gate_raw('gate_overwrite',1)"), '1',
	'abandoned physical I/O leaves conversion pending');
is($node->safe_psql('postgres', "SELECT gate_raw('gate_overwrite',2)"), '1',
	'explicit overwrite initializes a current-layout page without decoding legacy tuples');
is($node->safe_psql('postgres', "SELECT gate_raw('gate_overwrite',0)"), '1',
	'metadata-free read accepts a completed overwrite and discharges pending conversion');
$node->safe_psql('postgres', 'INSERT INTO gate_overwrite VALUES(9)');
is($node->safe_psql('postgres', 'TABLE gate_overwrite'), '9', 'overwritten page is usable');
is($node->safe_psql('postgres', "SELECT gate_raw('gate_forward',1,1)"), '1',
	'second block is physically complete but still needs conversion');
is($node->safe_psql('postgres', "SELECT gate_raw('gate_forward',3)"), '1',
	'split read completes both its waited block and its forwarded pending cache hit');
$node->safe_psql('postgres', "SELECT gate_attach('$injection_library','$dir')");
my $a = $node->background_psql('postgres');
$a->query_until(qr/writer_start/, qq{\\echo writer_start
SELECT gate_read('gate_table','$dir/writer_returned');
});
my $ready = 0;
for (1 .. 500)
{
	if (-e "$dir/entered") { $ready = 1; last; }
	sleep 0.01;
}
BAIL_OUT('converter did not reach partial publication') unless $ready;
my $buffer = slurp_file("$dir/entered");
chomp $buffer;
my $b = $node->background_psql('postgres');
$b->query_safe("SET application_name = 'gate_competing_reader'");
$b->query_until(qr/reader_start/, qq{\\echo reader_start
SELECT gate_read('gate_table','$dir/reader_returned');
});
for (1 .. 100)
{
	last if -e "$dir/reader_returned";
	last if $node->safe_psql('postgres', q{
		SELECT count(*) FROM pg_stat_activity
		WHERE application_name = 'gate_competing_reader' AND wait_event_type = 'LWLock'
	}) eq '1';
	sleep 0.01;
}
ok(!-e "$dir/reader_returned", 'cache-hit read cannot return during partial publication');
is($node->safe_psql('postgres', "SELECT gate_recent('gate_table',$buffer)"), 'f',
	'ReadRecentBuffer rejects a partially published page');
open(my $release, '>', "$dir/release") or die $!;
close($release) or die $!;
$a->query_safe('SELECT 1');
$b->query_safe('SELECT 1');
ok(-e "$dir/writer_returned" && -e "$dir/reader_returned",
	'both normal readers return after publication completes');
is($node->safe_psql('postgres', "SELECT gate_recent('gate_table',$buffer)"), 't',
	'ReadRecentBuffer accepts the completed conversion');
is($node->safe_psql('postgres', 'TABLE gate_table'), '42', 'converted tuple is intact');
$a->quit;
$b->quit;
$node->stop;
done_testing();

END
{
	if (defined $dir && !-e "$dir/release")
	{
		if (open(my $fh, '>', "$dir/release")) { close($fh); }
	}
}
