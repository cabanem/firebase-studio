# Firebase Studio configuration
## Notes
Firebase Studio is Google's browser-based dev environment (formerly 'Project IDX') that provisions your workspace from a single `.idx/dev.nix` file.
- Doesn't use `apt`, instead packages are declared with `Nix`.
- Studio builds the environment and installs components of the VM automatically.
- Editor extensions can also be pre-installed

**Key Functionality**
- `packages = [ ... ]` in `.idx/dev.nix` adds system tools (languages, compilers, libraries)
- `idx.extensions = [ ... ]` auto installs editor extensions from the **Open VSX** registry.
- Rebuild the environment from the Command Palatte (_"Firebase Studio: Rebuild Environment"_)
- A terminal is built-in
