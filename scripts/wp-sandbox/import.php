<?php
// Developer tool, not part of any theme. Runs the theme's synchronous
// whole-import function (SKILL.md step 8) — the CLI path — and prints what
// the site holds afterwards. The sliced admin-ajax path is exercised over
// HTTP, not here (verification.md, criterion 5b).
//   WP_ROOT=<sandbox>/wordpress IMPORT_FUNCTION=<slug>_run_import php import.php
if ( PHP_SAPI !== 'cli' ) { exit( 1 ); }

$root = getenv( 'WP_ROOT' );
$fn   = getenv( 'IMPORT_FUNCTION' );
if ( ! $root || ! $fn || ! file_exists( $root . '/wp-load.php' ) ) {
    fwrite( STDERR, "usage: WP_ROOT=<wordpress dir> IMPORT_FUNCTION=<function> php import.php\n" );
    exit( 2 );
}
require_once $root . '/wp-load.php';

// The command line has no user, and a request with no user cannot
// `unfiltered_html`, so kses is filtering post_content: every <form>, <input>,
// <select> and <textarea> the importer writes is silently dropped, and the
// pages arrive with forms that have labels and buttons and nothing between.
// Run as the administrator install.php created — wp_set_current_user() fires
// kses_init() again, which removes the filters for a user who may (pitfall #5d).
wp_set_current_user( (int) ( getenv( 'IMPORT_USER' ) ?: 1 ) );
if ( ! current_user_can( 'unfiltered_html' ) ) {
    fwrite( STDERR, "error: user " . get_current_user_id() . " cannot unfiltered_html — the import would lose every form control\n" );
    exit( 1 );
}

if ( ! function_exists( $fn ) ) {
    fwrite( STDERR, "error: $fn() is not defined — is the theme active, and is that its import function?\n" );
    exit( 1 );
}
$summary = call_user_func( $fn );
if ( is_array( $summary ) ) {
    $parts = array();
    foreach ( $summary as $k => $v ) {
        $parts[] = is_scalar( $v ) ? "$k=$v" : "$k=" . wp_json_encode( $v );
    }
    fwrite( STDOUT, 'import: ' . implode( ' ', $parts ) . "\n" );
}
fprintf( STDOUT, "front page: %s | posts page: %s | permalinks: %s\n",
    get_option( 'page_on_front' ), get_option( 'page_for_posts' ), get_option( 'permalink_structure' ) );
fprintf( STDOUT, "pages: %d | posts: %d | attachments: %d | categories: %d\n",
    wp_count_posts( 'page' )->publish, wp_count_posts( 'post' )->publish,
    count( get_posts( array( 'post_type' => 'attachment', 'numberposts' => -1, 'post_status' => 'inherit', 'fields' => 'ids' ) ) ),
    count( get_terms( array( 'taxonomy' => 'category', 'hide_empty' => false ) ) ) );
