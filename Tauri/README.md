# PortClear Tauri

This is the rewritten PortClear desktop app, using Tauri 2 + React/Vite + TypeScript.

The current goal is to rebuild the UI in a stack that is easier to maintain than the original Tkinter implementation, while reusing the proven behavior from `../Tkinter/` as the product reference.

## Stack

- Tauri 2 for the desktop shell and native system commands.
- React + TypeScript for the UI.
- Vite for development and frontend builds.

## Commands

Recommended pnpm workflow:

```bash
pnpm install
pnpm dev
pnpm tauri dev
pnpm tauri build
```

If pnpm is not installed yet:

```bash
npm install -g pnpm
```

Npm workflow:

```bash
npm install
npm run dev
npm run tauri dev
npm run tauri build
```

`pnpm tauri build` or `npm run tauri build` creates the Windows desktop bundles, including `.exe` output on Windows.

If dependency downloads are slow in China, use:

```bash
pnpm config set registry https://registry.npmmirror.com
pnpm install
```

## Structure

- `src/`: React application.
- `src-tauri/`: Tauri/Rust desktop backend.
- `../Tkinter/`: original implementation used as the behavior reference during the rewrite.
