import { readFileSync } from "node:fs";
import Module from "node:module";
import path from "node:path";
import ts from "typescript";

export function loadTypeScript(filename, imports = {}) {
  const loaded = new Module(filename);
  loaded.filename = filename;
  loaded.paths = Module._nodeModulePaths(path.dirname(filename));
  const require = loaded.require.bind(loaded);
  loaded.require = name => Object.hasOwn(imports, name) ? imports[name] : require(name);
  loaded._compile(ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true },
  }).outputText, filename);
  return loaded.exports;
}
