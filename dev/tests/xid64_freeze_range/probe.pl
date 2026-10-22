# A synthetic MultiXact jump exercises the normal-page freeze range limit.
# Never load this helper or edit offset files in a real cluster.
use strict;
use warnings FATAL => 'all';
use PostgreSQL::Test::Cluster;
use PostgreSQL::Test::Utils;
use Test::More;

my $node = PostgreSQL::Test::Cluster->new('freeze_range');
$node->init(extra => ['--multixact-id=1', '--multixact-offset=1']);
$node->append_conf('postgresql.conf', q{
autovacuum = off
autovacuum_freeze_max_age = 1000000000000
autovacuum_multixact_freeze_max_age = 1000000000000
restart_after_crash = off
});
$node->start;
my $lib = $ENV{XID64_FREEZE_RANGE_LIB};
$node->safe_psql('postgres', qq{
	CREATE FUNCTION test_jump_multixact(bigint, bigint) RETURNS void
	AS '$lib' LANGUAGE C STRICT;
	CREATE TABLE range_test(n int);
	INSERT INTO range_test VALUES(1);
});

my @locks;
for (1 .. 3)
{
	my $conn = $node->background_psql('postgres');
	$conn->query_safe('BEGIN; SELECT * FROM range_test FOR KEY SHARE;');
	push @locks, $conn;
}
my $b = $locks[1]->query_safe('SELECT pg_current_xact_id()');
my $c = $locks[2]->query_safe('SELECT pg_current_xact_id()');
$locks[0]->query_safe('COMMIT');
my $old_xmax = $node->safe_psql('postgres', 'SELECT xmax::text FROM range_test');
is($old_xmax, '2', 'fixture has an old MultiXact with three lockers');

# The native allocator preinitializes the current offset page while allocating
# its predecessor. A synthetic jump must supply that page explicitly. No
# members in the skipped range are referenced. This is not a recovery fixture.
my $blcksz = $node->safe_psql('postgres', 'SHOW block_size');
my $seg = int(2147484672 / ($blcksz / 8) / 32);
my $path = sprintf('%s/pg_multixact/offsets/%015X', $node->data_dir, $seg);
open(my $fh, '>:raw', $path) or die $!;
print $fh "\0" x ($blcksz * 32) or die $!;
close($fh) or die $!;
$node->safe_psql('postgres', "SELECT test_jump_multixact($b, $c)");

my ($ret, $out, $err) = $node->psql('postgres',
	'VACUUM (FREEZE, DISABLE_PAGE_SKIPPING) range_test');
is($ret, 3, 'unrepresentable replacement is a normal SQL error');
like($err, qr/cannot freeze tuple with an xmax outside the heap page's XID range/,
	'error identifies the page range limit');
like($err, qr/planned xmax 2147484672 with page base 0/,
	'error reports the actual replacement and existing base');
is($node->safe_psql('postgres', 'SELECT 1'), '1',
	'server continues accepting queries');
is($node->safe_psql('postgres', 'SELECT xmax::text FROM range_test'), $old_xmax,
	'failed freeze did not install the replacement xmax');
is($node->safe_psql('postgres', 'TABLE range_test'), '1',
	'row remains visible');

for my $conn (@locks)
{
	$conn->quit;
}
is($node->psql('postgres', 'VACUUM (FREEZE, DISABLE_PAGE_SKIPPING) range_test'),
	0, 'VACUUM succeeds after the remaining lockers finish');
is($node->safe_psql('postgres', 'SELECT xmax::text FROM range_test'), '0',
	'finished lock-only MultiXact is removed');
is($node->safe_psql('postgres', 'TABLE range_test'), '1',
	'row survives the successful retry');
$node->stop;
done_testing();
