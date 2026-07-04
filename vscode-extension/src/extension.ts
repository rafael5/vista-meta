// VistA Compass VSCode extension — activation + wiring only.
// All data comes from a schema_version 1 vista-meta data root (the
// repo's vista/export tree or an unpacked vista-meta-data-v1 release
// bundle). We never parse MUMPS, never hit the container, never
// depend on the internet.

import * as vscode from 'vscode';
import { VistaCompassHoverProvider } from './hover';
import { RoutineTreeProvider } from './treeProvider';
import { clearIndexes, dataVintage, reloadAll } from './tsv';
import { clearGlobalBaseIndex } from './hover';

export function activate(ctx: vscode.ExtensionContext): void {
  const provider = new RoutineTreeProvider();

  const view = vscode.window.createTreeView('vistaCompassRoutine', {
    treeDataProvider: provider,
    showCollapseAll: true,
  });
  ctx.subscriptions.push(view);

  // Surface the vintage of the data being read (V7 manifest.json in an
  // unpacked data-v1 bundle; V3 column manifest in the dev tree) and
  // warn once if the schema major doesn't match what this build reads.
  const showVintage = (): void => {
    const v = dataVintage();
    view.description = v?.label ?? '';
    if (v?.detail) view.message = undefined;
    if (v && v.schemaVersion !== null && v.schemaVersion !== 1) {
      vscode.window.showWarningMessage(
        `VistA Compass reads schema_version 1 data; the data root declares ` +
          `schema_version ${v.schemaVersion} — columns may not line up.`,
      );
    }
  };
  showVintage();

  ctx.subscriptions.push(
    vscode.languages.registerHoverProvider(
      [
        { language: 'mumps', scheme: 'file' },
        { pattern: '**/*.m', scheme: 'file' },
      ],
      new VistaCompassHoverProvider(),
    ),
  );

  // Update the sidebar whenever the active editor changes to a .m file
  const updateFromActiveEditor = (): void => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      provider.setActiveFile(null);
      return;
    }
    const doc = editor.document;
    if (doc.uri.scheme !== 'file' || !doc.fileName.endsWith('.m')) {
      provider.setActiveFile(null);
      return;
    }
    provider.setActiveFile(doc.fileName);
  };

  ctx.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(updateFromActiveEditor),
  );
  updateFromActiveEditor();

  ctx.subscriptions.push(
    vscode.commands.registerCommand('vistaCompass.refresh', () => {
      provider.refresh();
    }),
    vscode.commands.registerCommand('vistaCompass.reloadTsvs', () => {
      reloadAll();
      clearIndexes();
      clearGlobalBaseIndex();
      provider.refresh();
      showVintage();
      const v = dataVintage();
      vscode.window.showInformationMessage(
        `VistA Compass: TSVs reloaded${v ? ` (${v.label})` : ''}`,
      );
    }),
  );
}

export function deactivate(): void { /* no-op */ }
