// VistA Compass VSCode extension — activation + wiring only.
// All data lives in TSVs under vista/export/code-model/. We never
// parse MUMPS, never hit the container, never depend on the internet.

import * as vscode from 'vscode';
import { VistaCompassHoverProvider } from './hover';
import { RoutineTreeProvider } from './treeProvider';
import { clearIndexes, reloadAll } from './tsv';

export function activate(ctx: vscode.ExtensionContext): void {
  const provider = new RoutineTreeProvider();

  const view = vscode.window.createTreeView('vistaCompassRoutine', {
    treeDataProvider: provider,
    showCollapseAll: true,
  });
  ctx.subscriptions.push(view);

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
      provider.refresh();
      vscode.window.showInformationMessage('VistA Compass: TSVs reloaded');
    }),
  );
}

export function deactivate(): void { /* no-op */ }
