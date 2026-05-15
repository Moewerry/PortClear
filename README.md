# PortClear

PortClear now keeps the original Tkinter/Python implementation and the Tauri rewrite side by side.

## Project Layout

- `Tkinter/`: original Python implementation, including the existing Windows GUI, Linux CLI, build scripts, docs, and packaged artifacts.
- `Tauri/`: new Tauri 2 + React/Vite + TypeScript rewrite.

## Original Version

Run the existing implementation from the `Tkinter/` directory:

```bash
cd Tkinter
python main.py
```

## Rewrite

Use `Tauri/` for the new version:

```bash
cd Tauri
pnpm install
pnpm tauri dev
```

Build a Windows desktop package:

```bash
pnpm tauri build
```

If pnpm is not installed yet:

```bash
npm install -g pnpm
```

The npm equivalents are `npm install`, `npm run tauri dev`, and `npm run tauri build`.

Rust/Cargo is required for Tauri development and packaging.
