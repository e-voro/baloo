#!/usr/bin/perl
# File name: patch_ripper.pl
# Creation date: 18.11.2024
# Author: Evgeny Voropaev <evorop@gmail.com>

use strict;
use warnings;
use File::Basename;
use File::Spec;
use Cwd 'abs_path';

# Set strict error handling
use autodie;

# Calculate the project directory relative to the script location
my $script_dir = dirname(__FILE__);
my $PROJ_DIR = File::Spec->catdir($script_dir, '../../..');
my $BALOO_DIR = File::Spec->catdir($PROJ_DIR, 'baloo');

# Check if correct number of arguments is provided
if (@ARGV != 1) {
    die "Input patch is not defined. Usage: $0 <input_patch>\n";
}

my $input_patch_name = $ARGV[0];
my $input_patch_dir = dirname($input_patch_name);

# Check if input patch exists
unless (-e $input_patch_name) {
    die "Error: Patch file '$input_patch_name' does not exist.\n";
}

open(my $in, '<', $input_patch_name);

my $output_patch_dir = $input_patch_dir . "/ripped/";
mkdir($output_patch_dir);
my $output_patch_name = $output_patch_dir . "patchheader.txt";
open(my $out, '>', $output_patch_name);

my $patched_file_name;
while (my $line = <$in>) {
    if ( $line =~ /^diff --git/ ) {
        ($patched_file_name) = ($line =~ /(?<=b\/)(.*)$/);
        $output_patch_name = $output_patch_dir . get_output_patch_name($patched_file_name);
        close $out;
        open($out, '>>', $output_patch_name);
    }
    print $out "$line";
}

sub get_output_patch_name { 
    my ($patched_file_name) = @_;
    my @units = (
	    ["transam", "src/backend/access/transam", "src/include/access/transam"], 
	    ["heap",    "src/backend/access/heap", "src/include/access/heap"], 
	    ["access",  "src/backend/access/", "src/include/access/"], 
	    ["buffer",  "src/backend/storage/buffer", "src/include/storage/buf"], 
	    ["storage", "src/backend/storage", "src/include/storage"], 
	    ["utils",   "src/backend/utils", "src/include/utils"], 
	    ["backend", "src/backend/"],
	    ["bin",     "src/bin/"],
	    ["common",  "src/common/"],
	    ["test",    "src/test/"], 
        ["src",     "src/"],
        ["contrib", "contrib/"],
        ["doc",     "doc/"],
    );

    for my $u ( 0 .. $#units ) {
        for my $p ( 1 .. $units[$u]->$#* ) {
            if ( $patched_file_name =~ /^$units[$u][$p]/ ) {
                return $units[$u][0] . ".patch";
            }
        }
    }

    return "other.patch";
}