{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/release-26.05";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      eachSystem = nixpkgs.lib.genAttrs systems;
      toolchain = pkgs: pkgs.texlive.combine {
        inherit (pkgs.texlive) scheme-small amsmath amsfonts dvipng;
      };
      pythonDeps = ps: with ps; [ textual textual-image pillow cairosvg defusedxml ];
    in {
      packages = eachSystem (system:
        let pkgs = import nixpkgs { inherit system; }; in {
          default = self.packages.${system}.corrugate;
          corrugate = pkgs.python3Packages.buildPythonApplication {
            pname = "corrugate";
            version = "0.1.0";
            pyproject = true;
            src = pkgs.lib.cleanSource ./.;
            build-system = [ pkgs.python3Packages.setuptools ];
            dependencies = pythonDeps pkgs.python3Packages;
            nativeBuildInputs = [ pkgs.makeWrapper ];
            nativeCheckInputs = [ pkgs.python3Packages.pytestCheckHook ];
            pythonImportsCheck = [ "corrugate" ];
            preCheck = ''export PATH=${pkgs.lib.makeBinPath [ (toolchain pkgs) ]}:$PATH'';
            postInstall = ''
              mkdir -p $out/share/corrugate
              cp -r plugin $out/share/corrugate/plugin
            '';
            postFixup = ''
              wrapProgram $out/bin/corrugate --prefix PATH : ${pkgs.lib.makeBinPath [ (toolchain pkgs) pkgs.kitty ]}
            '';
            meta = {
              description = "A persistent visual whiteboard beside Codex in Kitty";
              mainProgram = "corrugate";
              license = pkgs.lib.licenses.asl20;
              platforms = systems;
            };
          };
        });
      devShells = eachSystem (system:
        let pkgs = import nixpkgs { inherit system; }; in {
          default = pkgs.mkShell {
            packages = [
              (pkgs.python3.withPackages (ps: pythonDeps ps ++ [ ps.pytest ps.pytest-asyncio ps.pyyaml ps.setuptools ]))
              (toolchain pkgs)
              pkgs.kitty
              pkgs.ruff
            ];
            shellHook = ''export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"'';
          };
        });
      checks = eachSystem (system: { inherit (self.packages.${system}) corrugate; });
    };
}
