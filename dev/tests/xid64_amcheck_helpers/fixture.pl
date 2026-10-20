use strict;
use warnings FATAL => 'all';
use File::Temp qw(tempfile);
use Test::More;

# PRODUCTION HELPERS

sub bytes_at
{
	my ($fh, $offset, $length) = @_;
	defined(sysseek($fh, $offset, 0)) or die "seek: $!";
	my $buffer;
	sysread($fh, $buffer, $length) == $length or die "read: $!";
	return $buffer;
}

my $old_xid_base = 4294968296;
my $old_multi_base = 8589936592;
my $start = HEAPPAGE_SIZE;
my $end = 2 * HEAPPAGE_SIZE;
my @raw = ([0, 0, 0], [1, 1, 0], [2, 2, 0], [3, 7, 0],
	[1, 2, HEAP_XMAX_IS_MULTI], [11, 13, HEAP_XMAX_IS_MULTI]);
my @offsets = map { $start + 128 + 64 * $_ } (0 .. $#raw);
push @offsets, $end - HEAPPAGE_SPECIAL_PACK_LENGTH - HEAPTUPLE_PACK_LENGTH;
push @raw, [17, 19, 0];

for my $hint (0, 1, 2, 7, MAX_SHORT_TRANSACTION_ID - 50)
{
	my ($fh, $path) = tempfile(UNLINK => 1);
	binmode $fh;
	syswrite($fh, "\0" x (3 * HEAPPAGE_SIZE)) == 3 * HEAPPAGE_SIZE
	  or die "initial write";
	for my $page (0 .. 2)
	{
		write_special_data($fh, $page * HEAPPAGE_SIZE,
			{ pd_xid_base => $old_xid_base, pd_multi_base => $old_multi_base });
	}
	my $hint_offset = $start + HEAPPAGE_PRUNE_XID_OFFSET;
	sysseek($fh, $hint_offset, 0) or die "seek hint";
	syswrite($fh, pack('L', $hint)) == 4 or die "write hint";
	for my $i (0 .. $#offsets)
	{
		my $tuple = read_tuple($fh, $offsets[$i], 1);
		@$tuple{qw(t_xmin t_xmax t_infomask)} = @{ $raw[$i] };
		write_tuple($fh, $offsets[$i], $tuple, 1);
	}
	my @full;
	for my $i (0 .. $#offsets)
	{
		my $tuple = read_tuple($fh, $offsets[$i]);
		my $xmin = $raw[$i][0];
		my $xmax = $raw[$i][1];
		$xmin += $old_xid_base if $xmin >= 3;
		$xmax += ($raw[$i][2] & HEAP_XMAX_IS_MULTI) ?
		  $old_multi_base : $old_xid_base if $xmax >= 3;
		is_deeply([@$tuple{qw(t_xmin t_xmax)}], [$xmin, $xmax],
			'decode preserves reserved IDs and reconstructs high XIDs');
		my %before = %$tuple;
		my $wire = bytes_at($fh, $offsets[$i], HEAPTUPLE_PACK_LENGTH);
		write_tuple($fh, $offsets[$i], $tuple);
		write_tuple($fh, $offsets[$i], $tuple);
		is_deeply($tuple, \%before, 'writing does not mutate caller full XIDs');
		is(bytes_at($fh, $offsets[$i], HEAPTUPLE_PACK_LENGTH), $wire,
			'repeated write round trips exact tuple bytes');
		push @full, [$xmin, $xmax];
	}
	my $previous = bytes_at($fh, 0, HEAPPAGE_SIZE);
	my $following = bytes_at($fh, $end, HEAPPAGE_SIZE);
	fixup_page($fh, 1, $old_xid_base - 100, $old_multi_base - 200,
		[-1, 128, $start - 1, @offsets, $end, $end + 128]);
	is(bytes_at($fh, 0, HEAPPAGE_SIZE), $previous, 'previous page unchanged');
	is(bytes_at($fh, $end, HEAPPAGE_SIZE), $following,
		'following page unchanged, including exact end boundary');
	for my $i (0 .. $#offsets)
	{
		my $tuple = read_tuple($fh, $offsets[$i]);
		is_deeply([@$tuple{qw(t_xmin t_xmax)}], $full[$i],
			'rebasing preserves full XIDs and MultiXacts');
		my $raw_tuple = read_tuple($fh, $offsets[$i], 1);
		for my $field (0, 1)
		{
			next if $raw[$i][$field] >= 3;
			is($raw_tuple->{$field ? 't_xmax' : 't_xmin'}, $raw[$i][$field],
				'rebasing preserves reserved disk value');
		}
	}
	my $expected_hint = $hint < 3 ? $hint : $hint + 100;
	$expected_hint = 2 if $expected_hint > MAX_SHORT_TRANSACTION_ID;
	is(unpack('L', bytes_at($fh, $hint_offset, 4)), $expected_hint,
		'hint preserves full XID or requests conservative retry');
	my $page = bytes_at($fh, $start, HEAPPAGE_SIZE);
	fixup_page($fh, 1, $old_xid_base - 100, $old_multi_base - 200, \@offsets);
	is(bytes_at($fh, $start, HEAPPAGE_SIZE), $page, 'same-base fixup is a no-op');
	my $ok = eval {
		fixup_page($fh, 1, $old_xid_base - 101, $old_multi_base - 200, [$end - 1]);
		1;
	};
	ok(!$ok && $@ =~ /overlaps page special data/,
		'reject a tuple that would cross the page boundary');
	is(bytes_at($fh, 0, 3 * HEAPPAGE_SIZE), $previous . $page . $following,
		'invalid tuple boundary leaves the file unchanged');
}

for my $case ([3, -1], [MAX_SHORT_TRANSACTION_ID, 1])
{
	my $ok = eval { shift_short_xid(@$case); 1 };
	ok(!$ok && $@ =~ /does not fit/, 'reject unrepresentable tuple rebase');
}
done_testing();
