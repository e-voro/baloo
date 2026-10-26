use strict;
use warnings FATAL => 'all';
use PostgreSQL::Test::Cluster;
use PostgreSQL::Test::Utils;
use Test::More;

my $node = PostgreSQL::Test::Cluster->new('hsf_protocol');
$node->init(allows_streaming => 1, extra => ['--xid=4294967396']);
$node->start;
my $xmin = $node->safe_psql('postgres', 'SELECT pg_current_xact_id()::text');
cmp_ok($xmin, '>', 4294967295, 'feedback test uses a full XID above 32 bits');
my $client = $ENV{XID64_HSF_CLIENT};
command_ok([$client, $node->connstr('postgres'), 'H', $xmin],
 'new feedback tag reaches the real walsender and retains the full xmin');
command_ok([$client, $node->connstr('postgres'), 'Hfuture', '18446744073709551615'],
 'future full xmin is ignored without installing a horizon');
command_ok([$client, $node->connstr('postgres'), 'Hcatalog', '18446744073709551615'],
 'future full catalog_xmin is ignored without installing a horizon');
for my $tag ('h', 'H+')
{
 my ($stdout, $stderr) = ('', '');
 my $ok = IPC::Run::run([$client, $node->connstr('postgres'), $tag, $xmin],
  '>', \$stdout, '2>', \$stderr);
 ok(!$ok && ($? >> 8) == 2, "$tag is rejected by the real feedback dispatcher");
 like($stderr, qr/server closed feedback connection/, 'rejection closes the replication stream');
}
like(slurp_file($node->logfile),
 qr/legacy hot standby feedback is incompatible with 64-bit transaction IDs/,
 'legacy format has an explicit incompatibility diagnostic');
like(slurp_file($node->logfile), qr/invalid message format/,
 'new-format messages reject trailing payload bytes');
is($node->safe_psql('postgres', 'SELECT 1'), '1', 'protocol rejection leaves the server available');
$node->stop;
if (defined $ENV{XID64_HSF_LEGACY_INSTALL})
{
 my $legacy = PostgreSQL::Test::Cluster->new('legacy_hsf',
  install_path => $ENV{XID64_HSF_LEGACY_INSTALL});
 $legacy->init(allows_streaming => 1, force_initdb => 1, xid32 => 1);
 $legacy->start;
 my ($stdout, $stderr) = ('', '');
 my $ok = IPC::Run::run([$client, $legacy->connstr('postgres'), 'H', $xmin],
  '>', \$stdout, '2>', \$stderr);
 ok(!$ok && ($? >> 8) == 2, 'legacy walsender rejects the xid64 tag before decoding');
 like(slurp_file($legacy->logfile), qr/unexpected message type "H"/,
  'legacy dispatcher reports the unknown tag');
 is($legacy->safe_psql('postgres', 'SELECT 1'), '1', 'legacy server remains available');
 $legacy->stop;
}
done_testing();
