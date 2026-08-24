# DataForge

Offline visual data assembly for Android and desktop. DataForge imports CSV, TSV, JSON, and SQLite projects, lets you build joins and transformations without hand-writing SQL, and exports usable tables, charts, CSV, JSON, or a complete SQLite database.

No account, server, database service, or network connection is required after installation.

## Try it

Desktop (Python 3.10+ with Tk):

```bash
./run_desktop.sh
```

Build the Android APK (Node 18+, Java, `npm`, and `zip`):

```bash
./build_android.sh
```

The tested APK is also published under [GitHub Releases](../../releases). Workflow artifacts are retained for build inspection; Releases are the normal download route.

## What it does

- imports CSV, TSV, JSON, and SQLite projects
- creates blank typed tables
- connects tables with visual `LEFT` and `INNER` joins
- selects, renames, filters, groups, sorts, aggregates, and deduplicates outputs
- previews the generated parameterized SQL
- saves reusable query plans in `_dataforge_queries`
- materializes results as SQLite tables
- renders bar, line, and pie charts
- exports CSV, JSON, or the full SQLite project
- seeds a disposable three-table example only when a project is new and empty

Nested JSON objects and arrays are preserved as JSON text in SQLite cells. Imported values are inferred as `INTEGER`, `REAL`, or `TEXT`.

## Android

DataForge 1.0.3 uses a self-contained legacy ASM.js SQLite build. It does not load WebAssembly, fetch SQLite at runtime, or send project data over the network. The Android system picker handles imports; projects persist in the application sandbox.

The clean public application ID is `app.dataforge.mobile`. This intentionally installs separately from historical testing builds.

## Desktop

The native desktop UI uses Tk and Python's built-in SQLite module—no browser or local web server. Its default project path is `~/DataForge/default.dataforge.sqlite`; **New**, **Open**, and **Backup** provide explicit project-file control.

## Verification

```bash
./test.sh
```

The checks exercise the Python query engine, validate generated joins and materialization, parse Android assets, verify JavaScript syntax, check the APK when present, and reject private or signing material.

## Honest limits

- the Android preview grid displays at most 2,000 rows; the desktop preview displays at most 5,000
- large imports are memory-bound on phones because SQLite runs inside the local WebView process
- the visual builder supports common joins and aggregates, not every SQLite expression
- Android releases are unsigned debug-compatible builds from CI; verify the published SHA-256 before installing
- the app does not connect directly to remote MySQL or PostgreSQL servers

## Support and funded direction

If DataForge saves you time, see [SUPPORT.md](SUPPORT.md). A confirmed public donation can be referenced in a GitHub issue to request development priority. Donations do not guarantee implementation, support, ownership, returns, or a deadline.

## License

MIT. The bundled SQL.js/SQLite component retains its upstream license notice in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).


## Install and run

```sh
chmod +x install.sh run.sh
./install.sh
./run.sh --help
```
