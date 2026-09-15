<?php
// Developer tool, not part of any theme. Run from the command line by setup.sh:
//   WP_ROOT=<sandbox>/wordpress THEME_SLUG=<slug> [SITE_TITLE=…] [ADMIN_PASSWORD=…] php install.php
if ( PHP_SAPI !== 'cli' ) { exit( 1 ); }

$root = getenv( 'WP_ROOT' );
$slug = getenv( 'THEME_SLUG' );
if ( ! $root || ! $slug || ! file_exists( $root . '/wp-load.php' ) ) {
    fwrite( STDERR, "usage: WP_ROOT=<wordpress dir> THEME_SLUG=<slug> php install.php\n" );
    exit( 2 );
}

define( 'WP_INSTALLING', true );
require_once $root . '/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/upgrade.php';

if ( ! is_blog_installed() ) {
    $r = wp_install(
        getenv( 'SITE_TITLE' ) ?: 'Sandbox',
        getenv( 'ADMIN_USER' ) ?: 'admin',
        getenv( 'ADMIN_EMAIL' ) ?: 'admin@example.test',
        true,
        '',
        getenv( 'ADMIN_PASSWORD' ) ?: 'admin-password'
    );
    fwrite( STDOUT, "installed: user {$r['user_id']}\n" );
} else {
    fwrite( STDOUT, "already installed\n" );
}

if ( ! wp_get_theme( $slug )->exists() ) {
    fwrite( STDERR, "error: no theme '$slug' under wp-content/themes — did sync.sh run?\n" );
    exit( 1 );
}
switch_theme( $slug );
fwrite( STDOUT, 'active theme: ' . get_option( 'stylesheet' ) . "\n" );
