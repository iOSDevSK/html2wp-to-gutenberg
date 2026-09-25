#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""The sibling block theme, scaffolded the way an official one is laid out.

    python3 scaffold-theme.py --old <html2wp-theme> --tokens tokens.json \\
        --out <new-theme> --slug mara-vidal-blocks --name "Mara Vidal Blocks" \\
        --css assets/styles.css [--js assets/spa-runtime.js] [--fonts-url URL] \\
        [--media-url __THEME_URI__/assets/images] [--presets on|off] [--layout on|off] \\
        [--author NAME] [--version 2.0.0] [--chrome front-page]

What it writes (SKILL.md steps 2, 4, 6; convert-source.py does the pages):

  theme.json     v3, the design tokens as presets (extract-tokens.py): palette,
                 font families, font sizes, spacing scale — core's own
                 defaults off — contentSize/wideSize from the design's centred
                 width, and a root block gap of 0 with blockGap on, so every
                 gap is a block's own preset and nothing is implied
  templates/     Twenty Twenty-Five's set in the design's page shell (a group
                 with its own classes) around the header part, a <main> group
                 and the footer part: page and front-page hold the post
                 content; index, home, archive, search, single and 404 are
                 built from the presets and the design's content rail
  parts/         header and footer, converted from the source's own chrome:
                 menus as core/navigation placements, the site's name as
                 core/site-title (content/menus.json, placements.json,
                 site.json; inc/navigation.php; editor-navigation.css)
  content/       every page source as block markup (convert-source.py), and
                 pages.json: each page's key, address and title
  inc/import.php the importer: an admin notice with one button (and a
                 function wp eval can call) that creates the pages — images
                 resolved from the __THEME_URI__ token, the front page and
                 pretty permalinks set, every page flagged so a re-import
                 updates its own and never an owner's
  <out>.reports/ beside the theme, not in it: convert-source.py's per-page
                 report (every class kept, and why)
  assets/        the design's stylesheet UNLAYERED and raised by one :root
                 (pitfall #3: core's layout rules are unlayered, so a layered
                 utility loses to them whatever its specificity), its :root
                 variables pointed at the presets they became, its scripts,
                 its images, and bridge.css — only what core's own wrappers
                 need (the <figure> an image gains, a background's padding)
  functions.php  enqueues all of it, the editor included; style.css and
                 readme.txt with the headers Theme Check requires (carried from
                 the source; an author it lacks comes from --author or stays out)

Exit 0; 2 = usage.
"""
import argparse
import datetime
import importlib.util
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def unlayer(css):
    """@layer x{…} → its rules, in place; `@layer a,b;` statements dropped.
    The source order IS the layer order a utility-first build emits (theme,
    base, components, utilities), so unwrapping keeps the design's cascade."""
    out, i, n = [], 0, len(css)
    while i < n:
        m = re.compile(r"@layer\b[^;{]*([;{])").search(css, i)
        if not m:
            out.append(css[i:])
            break
        out.append(css[i:m.start()])
        if m.group(1) == ";":
            i = m.end()
            continue
        depth, k = 1, m.end()
        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        out.append(unlayer(css[m.end():k - 1]))
        i = k
    return "".join(out)


def style_header(path):
    """A theme's style.css header fields ({"Author": "…", …}); empty values dropped."""
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    m = re.search(r"/\*(.*?)\*/", text, re.S)
    out = {}
    for line in (m.group(1) if m else "").splitlines():
        k, sep, v = line.partition(":")
        if sep and v.strip():
            out[k.strip()] = v.strip()
    return out


def compile_classes(tok_mod, css, classes, target):
    """The design's rules for these classes, re-aimed at one selector: every
    rule whose selector is one of the classes (with its pseudo-class or
    pseudo-element, inside its @media/@supports) becomes the same rule for
    target. Source order is kept, so the cascade between them is the design's."""
    wanted = set(classes)
    out = []
    for sel, body, ctx in tok_mod.rules(css):
        hits = []
        for one in sel.split(","):
            got = tok_mod.class_of(one)
            if got and got[0] in wanted:
                hits.append(target + got[1])
        if hits:
            rule = ",".join(hits) + "{" + body + "}"
            for at in reversed(ctx):
                rule = at + "{" + rule + "}"
            out.append(rule)
    return "\n".join(out) + ("\n" if out else "")


def point_at_presets(css, aliases):
    """The design's top-level :root variables read theme.json's presets
    (--ember:oklch(…) → --ember:var(--wp--preset--color--ember)), so the token
    is defined once and a colour or size changed in Styles reaches the classes
    that stayed classes as well as the blocks. Same value, so the page renders
    the same; a :root inside @media or @supports (a dark scheme, a fallback)
    is the design's own and is left alone."""
    if not aliases:
        return css
    names = "|".join(re.escape(k) for k in sorted(aliases, key=len, reverse=True))
    decl = re.compile(r"(?<![\w-])(" + names + r")\s*:[^;{}]*")
    spans, depth, boundary = [], 0, 0
    for m in re.finditer(r"[{};]", css):
        if m.group() == ";":
            if depth == 0:
                boundary = m.end()
            continue
        if m.group() == "}":
            depth -= 1
            if depth == 0:
                boundary = m.end()
            continue
        depth += 1
        end = css.find("}", m.end())
        if depth == 1 and "{" not in css[m.end():end] and \
                ":root" in [x.strip() for x in css[boundary:m.start()].split(",")]:
            spans.append((m.end(), end))
    for a, b in reversed(spans):
        css = css[:a] + decl.sub(lambda d: f"{d.group(1)}:{aliases[d.group(1)]}", css[a:b]) + css[b:]
    return css


BRIDGE = """/* Block bridge — only what core's own wrappers change (SKILL.md step 4). */
:root :where(.wp-block-image){margin:0}
:root .wp-block-image > img{display:block}
{images}{navigation}:root :where(.wp-block-group.has-background,p.has-background,h1.has-background,h2.has-background,h3.has-background,h4.has-background,h5.has-background,h6.has-background){padding:0}
:root :where(.wp-block-post-content,.wp-site-blocks){margin:0}
"""

IMPORT_PHP = """<?php
/**
 * The pages this theme ships, imported on request (SKILL.md step 8, its
 * synchronous core): content/pages.json names them, content/<key>.html holds
 * each one's block markup. Pages only — the images stay theme files, so the
 * whole import is one short request.
 *
 * Every page it creates carries the flag below, so a second import updates
 * its own pages and never an owner's; the reading and permalink settings it
 * claims are recorded once, before the first claim.
 *
 * @package __PKG__
 */

defined( 'ABSPATH' ) || exit;

const __UPREFIX___IMPORT_FLAG = '___PREFIX___imported';

/**
 * Import (or re-import) the shipped pages.
 *
 * @return array|WP_Error Counts, and every page left alone with the reason.
 */
function __PREFIX___import_pages() {
	$dir   = get_template_directory() . '/content';
	$pages = wp_json_file_decode( $dir . '/pages.json', array( 'associative' => true ) );
	if ( ! is_array( $pages ) ) {
		return new WP_Error( '__PREFIX___no_pages', __( 'The theme has no content/pages.json.', '__SLUG__' ) );
	}
	$state = get_option( '__PREFIX___import', array() );
	if ( ! isset( $state['site_options_before'] ) ) {
		$state['site_options_before'] = array(
			'show_on_front'       => get_option( 'show_on_front' ),
			'page_on_front'       => get_option( 'page_on_front' ),
			'permalink_structure' => get_option( 'permalink_structure' ),
		);
	}
	// The markup carries form controls and inline SVG in core/html blocks;
	// kses would strip them for a user without unfiltered_html, and the
	// command line has no user at all (pitfall #5d).
	kses_remove_filters();
	$uri    = get_template_directory_uri();
	$result = array(
		'created' => 0,
		'updated' => 0,
		'menus'   => 0,
		'skipped' => array(),
	);
	$front  = 0;
	foreach ( $pages as $page ) {
		$file = $dir . '/' . basename( $page['key'] ) . '.html';
		if ( ! is_readable( $file ) ) {
			$result['skipped'][ $page['slug'] ] = __( 'its file is missing from the theme', '__SLUG__' );
			continue;
		}
		$content  = str_replace( '__THEME_URI__', $uri, (string) file_get_contents( $file ) );
		$existing = get_page_by_path( $page['slug'], OBJECT, 'page' );
		$args     = array(
			'post_type'    => 'page',
			'post_status'  => 'publish',
			'post_title'   => $page['title'],
			'post_name'    => $page['slug'],
			'post_content' => $content,
		);
		if ( $existing && ! get_post_meta( $existing->ID, __UPREFIX___IMPORT_FLAG, true ) ) {
			$result['skipped'][ $page['slug'] ] = __( 'the address belongs to a page this theme did not create', '__SLUG__' );
			continue;
		}
		if ( $existing ) {
			$args['ID'] = $existing->ID;
			$id         = wp_update_post( wp_slash( $args ), true );
			$key        = 'updated';
		} else {
			$id  = wp_insert_post( wp_slash( $args ), true );
			$key = 'created';
		}
		if ( is_wp_error( $id ) ) {
			$result['skipped'][ $page['slug'] ] = $id->get_error_message();
			continue;
		}
		update_post_meta( $id, __UPREFIX___IMPORT_FLAG, 1 );
		++$result[ $key ];
		if ( ! empty( $page['front'] ) ) {
			$front = $id;
		}
	}
	kses_init();
	if ( $front ) {
		update_option( 'show_on_front', 'page' );
		update_option( 'page_on_front', $front );
	}
	// The pages link to each other as /about/: plain permalinks would 404
	// every one of them. Any other structure already serves pages there.
	if ( '' === get_option( 'permalink_structure' ) ) {
		global $wp_rewrite;
		$wp_rewrite->set_permalink_structure( '/%postname%/' );
		flush_rewrite_rules( false );
	}

	// The menus the parts place (content/menus.json): one wp_navigation post
	// each, its links to the pages just made, so the Navigation screen lists
	// them and one edit reaches every placement (pitfall #12b).
	$menus          = wp_json_file_decode( $dir . '/menus.json', array( 'associative' => true ) );
	$state['menus'] = isset( $state['menus'] ) ? $state['menus'] : array();
	foreach ( is_array( $menus ) ? $menus : array() as $menu ) {
		$links = '';
		foreach ( $menu['items'] as $item ) {
			$slug  = trim( $item['path'], '/' );
			$page  = '' === $slug ? ( $front ? get_post( $front ) : null ) : get_page_by_path( $slug, OBJECT, 'page' );
			$attrs = array( 'label' => $item['label'] );
			if ( $page ) {
				$attrs += array(
					'type' => 'page',
					'id'   => $page->ID,
					'url'  => get_permalink( $page ),
					'kind' => 'post-type',
				);
			} else {
				$attrs += array(
					'url'  => home_url( $item['path'] ),
					'kind' => 'custom',
				);
			}
			$links .= serialize_block(
				array(
					'blockName'    => 'core/navigation-link',
					'attrs'        => $attrs,
					'innerBlocks'  => array(),
					'innerHTML'    => '',
					'innerContent' => array(),
				)
			);
		}
		$existing = get_page_by_path( $menu['slug'], OBJECT, 'wp_navigation' );
		if ( $existing && ! get_post_meta( $existing->ID, __UPREFIX___IMPORT_FLAG, true ) ) {
			$result['skipped'][ $menu['slug'] ] = __( 'a menu of that name exists that this theme did not create', '__SLUG__' );
			continue;
		}
		$args = array(
			'post_type'    => 'wp_navigation',
			'post_status'  => 'publish',
			'post_title'   => $menu['name'],
			'post_name'    => $menu['slug'],
			'post_content' => $links,
		);
		if ( $existing ) {
			$args['ID'] = $existing->ID;
		}
		$id = $existing ? wp_update_post( wp_slash( $args ), true ) : wp_insert_post( wp_slash( $args ), true );
		if ( is_wp_error( $id ) ) {
			$result['skipped'][ $menu['slug'] ] = $id->get_error_message();
			continue;
		}
		update_post_meta( $id, __UPREFIX___IMPORT_FLAG, 1 );
		$state['menus'][ $menu['slug'] ] = $id;
		++$result['menus'];
	}

	// The site's name and tagline are what the header's site title shows:
	// the design's own words (content/site.json), the owner's recorded first.
	$site = wp_json_file_decode( $dir . '/site.json', array( 'associative' => true ) );
	if ( is_array( $site ) && ! empty( $site['name'] ) ) {
		foreach ( array( 'blogname', 'blogdescription' ) as $option ) {
			if ( ! array_key_exists( $option, $state['site_options_before'] ) ) {
				$state['site_options_before'][ $option ] = get_option( $option );
			}
		}
		update_option( 'blogname', $site['name'] );
		update_option( 'blogdescription', isset( $site['description'] ) ? $site['description'] : '' );
	}
	$state['imported'] = time();
	$state['version']  = wp_get_theme( get_template() )->get( 'Version' );
	$state['result']   = $result;
	update_option( '__PREFIX___import', $state, false );
	return $result;
}

add_action(
	'admin_post___PREFIX___import',
	static function () {
		if ( ! current_user_can( 'manage_options' ) || ! current_user_can( 'edit_pages' ) ) {
			wp_die( esc_html__( 'You are not allowed to import pages.', '__SLUG__' ) );
		}
		check_admin_referer( '__PREFIX___import' );
		$result = __PREFIX___import_pages();
		set_transient( '__PREFIX___import_notice', $result, 60 );
		wp_safe_redirect( admin_url( 'themes.php' ) );
		exit;
	}
);

add_action(
	'admin_notices',
	static function () {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		$done = get_transient( '__PREFIX___import_notice' );
		if ( false !== $done ) {
			delete_transient( '__PREFIX___import_notice' );
			if ( is_wp_error( $done ) ) {
				printf( '<div class="notice notice-error"><p>%s</p></div>', esc_html( $done->get_error_message() ) );
				return;
			}
			$lines = array();
			foreach ( $done['skipped'] as $slug => $why ) {
				/* translators: 1: page address, 2: reason */
				$lines[] = sprintf( esc_html__( '/%1$s/ was left alone: %2$s.', '__SLUG__' ), esc_html( $slug ), esc_html( $why ) );
			}
			$total = $done['created'] + $done['updated'];
			printf(
				'<div class="notice %1$s"><p>%2$s</p>%3$s</div>',
				$total ? 'notice-success' : 'notice-error',
				/* translators: 1: pages created, 2: pages updated, 3: menus */
				esc_html( sprintf( __( '__NAME__: %1$d pages created, %2$d updated; %3$d menus.', '__SLUG__' ), $done['created'], $done['updated'], isset( $done['menus'] ) ? $done['menus'] : 0 ) ),
				$lines ? '<p>' . implode( '<br>', $lines ) . '</p>' : ''
			);
			return;
		}
		// Offered until this version's pages are in: a newer theme over an
		// older one brings newer pages, and the owner is asked again.
		$state   = get_option( '__PREFIX___import', array() );
		$version = wp_get_theme( get_template() )->get( 'Version' );
		if ( ! empty( $state['imported'] ) && isset( $state['version'] ) && $state['version'] === $version ) {
			return;
		}
		$update = ! empty( $state['imported'] );
		printf(
			'<div class="notice notice-info"><p>%1$s</p><form method="post" action="%2$s"><input type="hidden" name="action" value="__PREFIX___import">%3$s<p><button class="button button-primary">%4$s</button></p></form></div>',
			esc_html(
				$update
					/* translators: 1: theme version, 2: number of pages */
					? sprintf( __( '__NAME__ %1$s brings new versions of its %2$d pages and its menus. Update them: what this theme created is replaced, what you made is left alone.', '__SLUG__' ), $version, __COUNT__ )
					/* translators: %d: number of pages */
					: sprintf( __( '__NAME__ ships %d pages and the menus its header and footer show. Import them to see the site as it was designed; the front page, the site name and pretty permalinks are set too.', '__SLUG__' ), __COUNT__ )
			),
			esc_url( admin_url( 'admin-post.php' ) ),
			wp_nonce_field( '__PREFIX___import', '_wpnonce', true, false ),
			$update ? esc_html__( 'Update the pages', '__SLUG__' ) : esc_html__( 'Import the pages', '__SLUG__' )
		);
	}
);
"""


NAVIGATION_PHP = """<?php
/**
 * The design's menus as core/navigation (SKILL.md step 6).
 *
 * content/placements.json lists where a menu appears in the parts: each
 * placement is a pattern registered here — a static part cannot carry the
 * menu's post ID, so the pattern resolves it (the importer records it) — and
 * the classes the design gives its links there. One menu, two placements,
 * one edit.
 *
 * @package __PKG__
 */

defined( 'ABSPATH' ) || exit;

/**
 * The placements, as scaffolded.
 *
 * @return array
 */
function __PREFIX___placements() {
	static $placements = null;
	if ( null === $placements ) {
		$placements = wp_json_file_decode( get_template_directory() . '/content/placements.json', array( 'associative' => true ) );
		$placements = is_array( $placements ) ? $placements : array();
	}
	return $placements;
}

add_action(
	'init',
	static function () {
		$state = get_option( '__PREFIX___import', array() );
		$menus = isset( $state['menus'] ) ? $state['menus'] : array();
		foreach ( __PREFIX___placements() as $placement ) {
			$attrs = $placement['block'];
			$id    = isset( $menus[ $placement['menu'] ] ) ? (int) $menus[ $placement['menu'] ] : 0;
			// Before the import there is no menu yet: core shows its fallback.
			if ( $id && 'wp_navigation' === get_post_type( $id ) && 'publish' === get_post_status( $id ) ) {
				$attrs = array( 'ref' => $id ) + $attrs;
			}
			register_block_pattern(
				'__SLUG__/navigation-' . $placement['id'],
				array(
					/* translators: %d: placement number */
					'title'    => sprintf( __( 'Navigation %d', '__SLUG__' ), $placement['id'] ),
					'inserter' => false,
					'content'  => '<!-- wp:navigation ' . serialize_block_attributes( $attrs ) . ' /-->',
				)
			);
		}
	}
);

// The design styles each link, not the list: its classes go on every item's
// <a> (the last one's own, when the design gives it its own — a call to
// action; the current page's, on the link core marks aria-current), core's
// item class steps aside so its colour and display rules do not outrank
// them, and a panel the old runtime toggles keeps the attributes it is
// driven by. The menu itself stays plain links.
add_filter(
	'render_block_core/navigation',
	static function ( $html, $block ) {
		$class = isset( $block['attrs']['className'] ) ? explode( ' ', (string) $block['attrs']['className'] ) : array();
		foreach ( __PREFIX___placements() as $placement ) {
			if ( ! in_array( $placement['marker'], $class, true ) ) {
				continue;
			}
			$count = new WP_HTML_Tag_Processor( $html );
			$total = 0;
			while ( $count->next_tag( array( 'class_name' => 'wp-block-navigation-item__content' ) ) ) {
				++$total;
			}
			$p = new WP_HTML_Tag_Processor( $html );
			if ( $p->next_tag( 'nav' ) ) {
				foreach ( $placement['attrs'] as $name => $value ) {
					$p->set_attribute( $name, '' === $value ? true : $value );
				}
			}
			$i = 0;
			while ( $p->next_tag( array( 'class_name' => 'wp-block-navigation-item__content' ) ) ) {
				++$i;
				$classes = ( $i === $total && '' !== $placement['last'] ) ? $placement['last'] : $placement['items'];
				if ( 'page' === $p->get_attribute( 'aria-current' ) ) {
					$classes .= ' ' . $placement['active'];
				}
				foreach ( preg_split( '/\\\\s+/', $classes, -1, PREG_SPLIT_NO_EMPTY ) as $name ) {
					$p->add_class( $name );
				}
				$p->remove_class( 'wp-block-navigation-item__content' );
			}
			return $p->get_updated_html();
		}
		return $html;
	},
	10,
	2
);
"""


FUNCTIONS = """<?php
/**
 * {name} — a block theme: the design lives in theme.json, the blocks use it.
 *
 * @package {pkg}
 */

defined( 'ABSPATH' ) || exit;

// The text is the source's, character for character: WordPress would curl
// its straight quotes and dashes, which the original never did.
add_filter( 'run_wptexturize', '__return_false' );

require_once __DIR__ . '/inc/import.php';
require_once __DIR__ . '/inc/navigation.php';

add_action(
	'after_setup_theme',
	static function () {{
		add_theme_support( 'editor-styles' );
		add_editor_style( array( {editor} ) );
	}}
);

add_action(
	'wp_enqueue_scripts',
	static function () {{
		$dir = get_template_directory();
		$uri = get_template_directory_uri();
{styles}
{scripts}
	}}
);
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--old", required=True)
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--css", action="append", required=True)
    ap.add_argument("--js", action="append", default=[])
    ap.add_argument("--fonts-url", default="")
    ap.add_argument("--media-url", default="__THEME_URI__/assets/images",
                    help="where the page images are; the default token is resolved by the importer")
    ap.add_argument("--version", default="2.0.0", help="the theme's Version header")
    ap.add_argument("--presets", choices=("on", "off"), default="on")
    ap.add_argument("--layout", choices=("on", "off"), default="on")
    ap.add_argument("--author", default="", help="the style.css Author when the source theme names none")
    ap.add_argument("--chrome", default="front-page", help="the source whose <header>/<footer> become the parts")
    args = ap.parse_args(argv)
    old, out = Path(args.old), Path(args.out)
    tokens = json.loads(Path(args.tokens).read_text())
    conv_mod = load("convert_source", "convert-source.py")
    raise_mod = load("raise_specificity", "raise-specificity.py")
    if out.exists():
        shutil.rmtree(out)
    reports = out.parent / f"{out.name}.reports"
    if reports.exists():
        shutil.rmtree(reports)
    reports.mkdir(parents=True)
    for d in ("templates", "parts", "content", "inc", "assets/images", "assets/js"):
        (out / d).mkdir(parents=True, exist_ok=True)

    # theme.json — the tokens as presets.
    lay = tokens.get("layout") or {}
    tj = {
        "$schema": "https://schemas.wp.org/wp/6.8/theme.json", "version": 3, "title": args.name,
        "settings": {
            "appearanceTools": True, "useRootPaddingAwareAlignments": False,
            "layout": {"contentSize": lay.get("contentSize", "1200px"), "wideSize": lay.get("wideSize", "1200px")},
            "color": {"defaultPalette": False, "defaultGradients": False, "defaultDuotone": False,
                      "palette": tokens["presets"]["palette"]},
            "typography": {"defaultFontSizes": False, "fluid": False, "fontFamilies": tokens["presets"]["fontFamilies"],
                           "fontSizes": tokens["presets"]["fontSizes"]},
            "spacing": {"blockGap": True, "defaultSpacingSizes": False, "spacingSizes": tokens["presets"]["spacingSizes"],
                        "units": ["px", "rem", "em", "%", "vw", "vh"]},
            "blocks": {"core/image": {"lightbox": {"enabled": False}}},
        },
        "styles": {"spacing": {"blockGap": "0px", "padding": {"top": "0px", "right": "0px", "bottom": "0px", "left": "0px"}}},
        "templateParts": [{"name": "header", "title": "Header", "area": "header"},
                          {"name": "footer", "title": "Footer", "area": "footer"}],
    }
    (out / "theme.json").write_text(json.dumps(tj, indent="\t") + "\n")
    # The headers Theme Check requires, carried from the source theme where it
    # has them; an author it lacks is not invented (--author supplies one).
    head = style_header(old / "style.css")
    author = args.author or head.get("Author", "")
    tested = head.get("Tested up to") or "7.0"
    description = (f"{args.name}: the {head.get('Theme Name') or old.name} design as a block theme. The design "
                   f"lives in theme.json, and every page is core blocks that use it.")
    fields = [("Theme Name", args.name), ("Theme URI", head.get("Theme URI", "")), ("Author", author),
              ("Author URI", head.get("Author URI", "")), ("Description", description),
              ("Requires at least", "6.6"), ("Tested up to", tested), ("Requires PHP", "7.4"), ("Version", args.version),
              ("License", "GNU General Public License v2 or later"),
              ("License URI", "https://www.gnu.org/licenses/gpl-2.0.html"), ("Text Domain", args.slug),
              ("Tags", "full-site-editing, custom-colors, editor-style")]
    (out / "style.css").write_text("/*\n" + "".join(f"{k}: {v}\n" for k, v in fields if v) + "*/\n")
    holder = author or f"the {head.get('Theme Name') or old.name} theme authors"
    (out / "readme.txt").write_text(
        f"=== {args.name} ===\nContributors: \nRequires at least: 6.6\nTested up to: {tested}\n"
        f"Requires PHP: 7.4\nStable tag: {args.version}\nLicense: GPLv2 or later\n"
        f"License URI: https://www.gnu.org/licenses/gpl-2.0.html\n\n{description}\n\n"
        f"== Description ==\n\n{description} Colours, type sizes and spacing are presets: change them in "
        f"Appearance > Editor > Styles and every block that uses them follows.\n\n"
        f"== Copyright ==\n\n{args.name} WordPress Theme, Copyright (C) {datetime.date.today().year} {holder}.\n"
        f"{args.name} is distributed under the terms of the GNU GPL v2 or later.\n")

    # The design's stylesheet, unlayered and raised; scripts; images.
    styles, editor = [], ["'assets/bridge.css'"]
    for i, c in enumerate(args.css):
        text = unlayer((old / c).read_text(encoding="utf-8"))
        text, _ = raise_mod.transform(text)
        if args.presets == "on":
            text = point_at_presets(text, tokens.get("aliases") or {})
        name = f"assets/site-{i}.css" if len(args.css) > 1 else "assets/site.css"
        (out / name).write_text(text, encoding="utf-8")
        styles.append(name)
        editor.append(f"'{name}'")
    # The bridge goes BEFORE the design, in the editor as on the page: it
    # beats core's own block styles (printed earlier still) and loses every
    # tie to the design's rules. The editor alone also gets the menus' link
    # styles (editor-navigation.css): on the page they are the link's classes.
    styles.insert(0, "assets/bridge.css")
    editor.append("'assets/editor-navigation.css'")
    for j in args.js:
        shutil.copy(old / j, out / "assets/js" / Path(j).name)
    for img in list(old.rglob("*.webp")) + list(old.rglob("*.png")) + list(old.rglob("*.jpg")) + list(old.rglob("*.jpeg")):
        if "screenshot" not in img.name and "/assets/images/" not in str(img):
            shutil.copy(img, out / "assets/images" / img.name)
    if (old / "screenshot.png").is_file():
        shutil.copy(old / "screenshot.png", out / "screenshot.png")
    pkg = re.sub(r"[^A-Za-z0-9]", "", args.name.title())
    style_lines = []
    for k, s in enumerate(styles):
        dep = f"array( '{args.slug}-{k - 1}' )" if k else ("array( 'google-fonts' )" if args.fonts_url else "array()")
        style_lines.append(f"\t\twp_enqueue_style( '{args.slug}-{k}', $uri . '/{s}', {dep}, filemtime( $dir . '/{s}' ) );")
    if args.fonts_url:
        style_lines.insert(0, f"\t\twp_enqueue_style( 'google-fonts', '{args.fonts_url}', array(), null );")
    script_lines = [f"\t\twp_enqueue_script( '{args.slug}-js-{k}', $uri . '/assets/js/{Path(j).name}', array(), "
                    f"filemtime( $dir . '/assets/js/{Path(j).name}' ), array( 'strategy' => 'defer' ) );"
                    for k, j in enumerate(args.js)]
    (out / "functions.php").write_text(FUNCTIONS.format(name=args.name, pkg=pkg, editor=", ".join(editor),
                                                        styles="\n".join(style_lines), scripts="\n".join(script_lines)))

    # Pages, then the chrome.
    summary = {}
    sources = sorted((old / "clara-content" / "sources").glob("*.html"))
    shells = {}
    for src in sources:
        target = out / "content" / src.name
        rc = conv_mod.main([str(src), "--tokens", args.tokens, "--out", str(target), "--presets", args.presets,
                            "--layout", args.layout, "--media-url", args.media_url])
        report = json.loads(Path(str(target) + ".report.json").read_text())
        Path(str(target) + ".report.json").rename(reports / (src.stem + ".report.json"))
        shells[src.stem] = report.get("shell")
        summary[src.stem] = report["blocks"]
    # What the importer creates: every page, its address and title as the
    # source bundle names them, the front page flagged.
    index = old / "clara-content" / "sources" / "index.json"
    rows = {r.get("key"): r for r in (json.loads(index.read_text()) if index.is_file() else [])}
    pages = []
    for src in sources:
        row = rows.get(src.stem) or {}
        front = src.stem == "front-page"
        pages.append({"key": src.stem, "slug": "home" if front else (row.get("slug") or src.stem),
                      "title": row.get("title") or src.stem.replace("-", " ").title(), "front": front})
    (out / "content" / "pages.json").write_text(json.dumps(pages, indent=2, ensure_ascii=False) + "\n")
    prefix = re.sub(r"[^a-z0-9]+", "_", args.slug.lower()).strip("_")
    (out / "inc" / "import.php").write_text(
        IMPORT_PHP.replace("__UPREFIX__", prefix.upper()).replace("__PREFIX__", prefix).replace("__SLUG__", args.slug).replace("__NAME__", args.name)
        .replace("__PKG__", re.sub(r"[^A-Za-z0-9]", "", args.name.title())).replace("__COUNT__", str(len(pages))))

    # An image's classes land on the <figure> core wraps it in: whatever
    # sized or fitted the <img> — a width, a height, an aspect ratio, object-fit
    # — now sizes the figure, and the image fills it. Rules for exactly the
    # classes the pages use, read off the design's own properties.
    image_classes = set()
    for f in (out / "content").glob("*.html"):
        for m in re.finditer(r'<figure class="wp-block-image ([^"]*)"', f.read_text(encoding="utf-8")):
            image_classes.update(m.group(1).split())
    fills = {"width": "width:100%", "height": "height:100%", "aspect-ratio": "width:100%;height:100%",
             "object-fit": "object-fit:inherit", "object-position": "object-position:inherit"}
    rules = {}
    for cls in sorted(image_classes):
        for prop in tokens["properties"].get(cls, []):
            if prop in fills:
                esc = re.sub(r"([^A-Za-z0-9_-])", r"\\\1", cls)
                rules.setdefault(fills[prop], []).append(f":root .wp-block-image.{esc} > img")
    images = "".join(",".join(sel) + "{" + decl + "}\n" for decl, sel in sorted(rules.items()))
    chrome_src = old / "clara-content" / "sources" / f"{args.chrome}.html"
    html = chrome_src.read_text(encoding="utf-8")
    tree = conv_mod.Tree(html)
    # The menus the bundle declares (menus.json), as the paths they link to:
    # a row of links in a part with the same paths, in order, is that menu.
    declared = old / "clara-content" / "menus.json"
    chrome = {"slug": args.slug, "menus": [], "placements": [], "site": {}}
    for m in (json.loads(declared.read_text()) if declared.is_file() else []):
        items = sorted(m.get("items") or [], key=lambda i: i.get("order") or 0)
        chrome["menus"].append({"slug": m["slug"], "name": m["name"],
                                "paths": [conv_mod.site_path(i.get("url")) for i in items],
                                "labels": [i.get("title") or "" for i in items]})
    conv = conv_mod.Converter(html, tokens, args.presets == "on", args.media_url, [], layout=args.layout == "on",
                              chrome=chrome)

    def first(node, tag):
        for ch in node.children:
            if isinstance(ch, conv_mod.Node):
                if ch.tag == tag:
                    return ch
                got = first(ch, tag)
                if got:
                    return got
        return None
    parts = {}
    for tag in ("header", "footer"):
        node = first(tree.root, tag)
        if node is None:
            continue
        (out / "parts" / f"{tag}.html").write_text("\n\n".join(conv.children(node)) + "\n")
        parts[tag] = node.classes()
    # What the importer and inc/navigation.php need: the menus the parts
    # place, where they are placed, the site's name. A placement's links are
    # laid out by its own element, as in the source: core's list and item
    # wrappers step aside (display:contents), and a panel that is not a flex
    # row stays a block.
    # The current page's link: the source marks it (a router's active state,
    # data-status="active" / aria-current="page") with classes of its own —
    # found on whichever page the link is current, and added at render time
    # to the link core marks aria-current.
    for pl in chrome["placements"]:
        pl["active"] = ""
        for src in sources:
            found = None
            stack = [conv_mod.Tree(src.read_text(encoding="utf-8")).root]
            while stack and found is None:
                n = stack.pop()
                kids = [k for k in n.children if isinstance(k, conv_mod.Node)]
                stack.extend(kids)
                if kids and n.classes() == pl["source"] and all(k.tag == "a" for k in kids) \
                        and [conv_mod.site_path(k.get("href")) for k in kids] == pl["paths"]:
                    for i, k in enumerate(kids):
                        if k.get("data-status") == "active" or k.get("aria-current") == "page":
                            base = set((pl["last"] if i == len(kids) - 1 and pl["last"] else pl["items"]).split())
                            found = " ".join(c for c in k.classes() if c not in base)
                            break
            if found:
                pl["active"] = found
                break
    menus = [{"slug": m["slug"], "name": m["name"],
              "items": [{"label": lab, "path": pth} for lab, pth in zip(m["labels"], m["paths"])]}
             for m in chrome["menus"] if m.get("used")]
    (out / "content" / "menus.json").write_text(json.dumps(menus, indent=2, ensure_ascii=False) + "\n")
    (out / "content" / "placements.json").write_text(json.dumps(chrome["placements"], indent=2, ensure_ascii=False) + "\n")
    if chrome["site"]:
        (out / "content" / "site.json").write_text(json.dumps(chrome["site"], indent=2, ensure_ascii=False) + "\n")
    nav_rules = ""
    for pl in chrome["placements"]:
        m = pl["marker"]
        nav_rules += (f":root body:not(.editor-styles-wrapper) .{m} .wp-block-navigation__container,"
                      f":root body:not(.editor-styles-wrapper) .{m} .wp-block-navigation-item{{display:contents}}\n")
        if pl["flow"]:
            nav_rules += f":root .{m}{{display:block}}\n"
    (out / "assets/bridge.css").write_text(BRIDGE.replace("{images}", images).replace("{navigation}", nav_rules))
    # In the editor no filter runs: the links are drawn by the design's own
    # rules for those classes, re-aimed at core's item markup.
    tok_mod = load("extract_tokens", "extract-tokens.py")
    design = "\n".join(tok_mod.strip_comments((old / c).read_text(encoding="utf-8")) for c in args.css)
    editor_css = []
    for pl in chrome["placements"]:
        base = f":root .{pl['marker']}.wp-block-navigation"
        item = " .wp-block-navigation-item:not(:last-child) > .wp-block-navigation-item__content" if pl["last"] \
            else " .wp-block-navigation-item__content"
        editor_css.append(compile_classes(tok_mod, design, pl["items"].split(), base + item))
        if pl["last"]:
            editor_css.append(compile_classes(tok_mod, design, pl["last"].split(),
                                              base + " .wp-block-navigation-item:last-child > .wp-block-navigation-item__content"))
    (out / "assets/editor-navigation.css").write_text("".join(editor_css))
    (out / "inc" / "navigation.php").write_text(
        NAVIGATION_PHP.replace("__PREFIX__", prefix).replace("__SLUG__", args.slug)
        .replace("__PKG__", re.sub(r"[^A-Za-z0-9]", "", args.name.title())))
    shell_node = first(tree.root, "header").parent if first(tree.root, "header") else None
    shell_classes = shell_node.classes() if shell_node is not None and shell_node.tag != "#root" else []
    main_classes = next((s["classes"] for s in shells.values() if s and s.get("tag") in ("main", "div")), [])

    def part(tag):
        a = {"slug": tag, "tagName": tag}
        if parts.get(tag):
            a["className"] = " ".join(parts[tag])
        return f"<!-- wp:template-part {conv_mod.wp_json(a)} /-->"
    main_attrs = {"tagName": "main"}
    if main_classes:
        main_attrs["className"] = " ".join(main_classes)
    main_attrs["layout"] = {"type": "default"}
    main_cls = " ".join(["wp-block-group"] + main_classes)

    def shell(body):
        inner = (f"{part('header')}\n\n<!-- wp:group {conv_mod.wp_json(main_attrs)} -->\n<main class=\"{main_cls}\">"
                 f"{body}</main>\n<!-- /wp:group -->\n\n{part('footer')}")
        if not shell_classes:
            return inner + "\n"
        shell_attrs = {"className": " ".join(shell_classes), "layout": {"type": "default"}}
        return (f"<!-- wp:group {conv_mod.wp_json(shell_attrs)} -->\n<div class=\"wp-block-group "
                f"{' '.join(shell_classes)}\">{inner}</div>\n<!-- /wp:group -->\n")

    # The canonical set (Twenty Twenty-Five's): pages and the front page are
    # the post content alone — the design's pages carry their own headings —
    # and the templates the source never had (a post, a listing, search, 404)
    # are built from the design's presets only: its type scale's largest and
    # middle sizes, its container padding, its spacing steps. No original to
    # diff them against; they are checked by eye in the Site Editor.
    sizes = [f["slug"] for f in tj["settings"]["typography"]["fontSizes"]]

    def step(rem):
        known = [(slug, float(re.sub(r"rem$", "", size))) for slug, size in
                 ((x["slug"], x["size"]) for x in tj["settings"]["spacing"]["spacingSizes"]) if size.endswith("rem")]
        return min(known, key=lambda k: abs(k[1] - rem))[0] if known else None
    pad_y = step(4)
    big, mid, small = (sizes[-1], sizes[len(sizes) // 2], sizes[0]) if sizes else (None, None, None)
    # The design's content rail: the classes its own centred sections carry
    # (a responsive side padding core cannot say), so a template's left edge
    # is the pages' left edge at every width.
    rails = Counter()
    for f in (out / "content").glob("*.html"):
        for m in re.finditer(r"<!-- wp:group (\{.*?\}) -->", f.read_text(encoding="utf-8")):
            a = json.loads(m.group(1))
            if (a.get("layout") or {}).get("type") == "constrained":
                rails[a.get("className", "")] += 1
    rail = rails.most_common(1)[0][0] if rails else ""
    pad_x = None if rail else (step(float(re.sub(r"px$", "", lay.get("padding", "32px"))) / 16) if lay.get("padding") else step(2))

    def fs(slug):
        """A preset size, with the line height the design gives that size."""
        if not slug:
            return {}
        lh = next((m["lineHeight"] for m in tokens["classes"].values()
                   if m.get("fontSize") == slug and m.get("lineHeight")), None)
        return {"fontSize": slug, **({"style": {"typography": {"lineHeight": lh}}} if lh else {})}

    def gap(rem):
        g = step(rem)
        return {"style": {"spacing": {"blockGap": f"var:preset|spacing|{g}"}}} if g else {}

    def section(body, tag="section"):
        """The design's rail around one column of blocks. The gaps are a grid's:
        the design's reset zeroes every margin, so core's margin-based block
        gap would not show (pitfall #3)."""
        pad = {k: f"var:preset|spacing|{v}" for k, v in (("top", pad_y), ("right", pad_x), ("bottom", pad_y),
                                                          ("left", pad_x)) if v}
        style = {"spacing": {"padding": pad}} if pad else {}
        a = {"tagName": tag, **({"className": rail} if rail else {}), **({"style": style} if style else {}),
             "layout": {"type": "constrained"}}
        cls = " ".join(["wp-block-group"] + ([rail] if rail else []))
        # A one-column grid, not a flex column: a listing's auto-fill grid
        # inside a flex column is sized at its min-content width and grows
        # thousands of pixels tall.
        col = {**gap(1.5), "layout": {"type": "grid", "columnCount": 1}}
        return (f"<!-- wp:group {conv_mod.wp_json(a)} -->\n<{tag} class=\"{cls}\"{conv.style_attr(style)}>"
                f"<!-- wp:group {conv_mod.wp_json(col)} -->\n<div class=\"wp-block-group\">{body}</div>\n<!-- /wp:group -->"
                f"</{tag}>\n<!-- /wp:group -->")

    def dyn(name, attrs=None):
        return f"<!-- wp:{name} {conv_mod.wp_json(attrs)} /-->" if attrs else f"<!-- wp:{name} /-->"

    def heading(text, level=1):
        a = {"level": level, **fs(big)}
        cls = "wp-block-heading" + (f" has-{big}-font-size" if big else "")
        return (f"<!-- wp:heading {conv_mod.wp_json(a)} -->\n<h{level} class=\"{cls}\"{conv.style_attr(a.get('style', {}))}>"
                f"{text}</h{level}>\n<!-- /wp:heading -->")

    def para(text):
        return f"<!-- wp:paragraph -->\n<p>{text}</p>\n<!-- /wp:paragraph -->"
    query = ("<!-- wp:query " + conv_mod.wp_json({"queryId": 1, "query": {"perPage": 12, "pages": 0, "offset": 0,
                                                                          "postType": "post", "order": "desc",
                                                                          "orderBy": "date", "inherit": True}})
             + " -->\n<div class=\"wp-block-query\">"
             + "<!-- wp:post-template " + conv_mod.wp_json({**gap(2.5), "layout": {"type": "grid", "minimumColumnWidth": "20rem"}})
             + " -->\n<!-- wp:group " + conv_mod.wp_json({**gap(0.5), "layout": {"type": "flex", "orientation": "vertical", "justifyContent": "stretch"}})
             + " -->\n<div class=\"wp-block-group\">"
             + dyn("post-featured-image", {"isLink": True, "aspectRatio": "4/3"}) + "\n\n"
             + dyn("post-date", fs(small)) + "\n\n"
             + dyn("post-title", {"level": 2, "isLink": True, **fs(mid)}) + "\n\n"
             + dyn("post-excerpt") + "</div>\n<!-- /wp:group -->\n<!-- /wp:post-template -->\n\n"
             + "<!-- wp:query-pagination " + conv_mod.wp_json({**gap(1), "layout": {"type": "flex", "justifyContent": "space-between"}})
             + " -->\n" + dyn("query-pagination-previous") + "\n\n"
             + dyn("query-pagination-numbers") + "\n\n" + dyn("query-pagination-next")
             + "\n<!-- /wp:query-pagination -->\n\n<!-- wp:query-no-results -->\n"
             + para("Nothing has been published here yet.") + "\n<!-- /wp:query-no-results --></div>\n<!-- /wp:query -->")
    border = next((c["slug"] for c in tj["settings"]["color"]["palette"] if c["slug"].startswith("border")), None)
    search = dyn("search", {"label": "Search", "showLabel": False, "buttonText": "Search",
                            "buttonPosition": "button-inside", "buttonUseIcon": True,
                            "style": {"border": {"width": "1px"}}, **({"borderColor": border} if border else {})})
    content = '<!-- wp:post-content {"layout":{"type":"default"}} /-->'
    templates = {
        "page": content,
        "front-page": content,
        "index": section(query),
        "home": section(query),
        "archive": section(dyn("query-title", {"type": "archive", **fs(big)}) + "\n\n" + query),
        "search": section(dyn("query-title", {"type": "search", **fs(big)}) + "\n\n"
                          + search + "\n\n" + query),
        "single": section(dyn("post-date", fs(small)) + "\n\n" + dyn("post-title", {"level": 1, **fs(big)}) + "\n\n"
                          + dyn("post-featured-image", {"aspectRatio": "16/9"}) + "\n\n"
                          + '<!-- wp:post-content {"layout":{"type":"constrained"}} /-->', "article"),
        "404": section(heading("Page not found") + "\n\n"
                       + para("The page you were looking for is not here. Try a search, or start from the home page.")
                       + "\n\n" + search),
    }
    for name, body in templates.items():
        (out / "templates" / f"{name}.html").write_text(shell(body))
    print(f"scaffold-theme: {out} — {len(sources)} page(s), parts {sorted(parts)}, presets {args.presets}; "
          f"theme.json {len(tj['settings']['color']['palette'])} colours, "
          f"{len(tj['settings']['typography']['fontSizes'])} sizes, {len(tj['settings']['spacing']['spacingSizes'])} spacing steps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
