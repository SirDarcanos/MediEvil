# Sources and attribution

## FrogLord

Map/resource format work is based on [Kneesnap/FrogLord](https://github.com/Kneesnap/FrogLord), revision `0cdc76e901c9dcea06061e151853cd3d1048f95d`:

- `resources/games/medievil/versions/ntsc-u-master.cfg`
- `MediEvilLevelTableEntry.java`, `MediEvilMapGraphicsPacket.java`, `MediEvilMapPolygon.java`
- `MWIResourceEntry.java`, `WADFile.java`, `PP20Unpacker.java`, `SVector.java`
- `VloFile.java`, `VloImage.java`, `VloClut.java`, `VloClutList.java`: texture/palette decoding, image content rectangles and VRAM-relative UV origins
- `MediEvilMapPolygon.java`, `SCByteTextureUV.java`: polygon UV ordering. The renderer's first-row V origin was checked separately against rendered landmarks and recorded game-loaded UVs; the Java comment about reversing V is not used as authority for our PNG pipeline.
- `MediEvilMapEntitiesPacket.java`, `MediEvilMapEntity.java`, `MediEvilEntityDefinition.java`: static entity positions and subtype/model assignments
- `MediEvilMapCollprim.java`, `MediEvilMapCollprimsPacket.java`, `MediEvilMapGridPacket.java`, `MediEvilMapGridSquare.java`: collision-volume and spatial-grid layouts (exit classification independently traced in the executable)

- `MRStaticMof.java`, `MRMofPart.java`, `MRMofPartCel.java`, `MRMofPolygon.java`, `MRMofPolygonType.java`, `MRMofPolygonBlock.java`: supported static MOF parts/primitives and vertex/UV pairing
- `MediEvilEntityTable.java`, `SCOverlayTableEntry.java`, `MediEvilEntityManager.java`: level-mask/overlay definition lookup and authored model placement/rotation
- `MediEvilScripter.java`: event-script record layouts, condition/command identities and flags; exit semantics are checked separately against the executable and overlays

The Python extractor is a small adaptation of those format definitions/algorithms, not a FrogLord runtime dependency. FrogLord’s MIT notice is reproduced below.

> MIT License
>
> Copyright (c) 2018-2024 Kneesnap
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

## Runner distribution

The runner ZIP contains format-handling code and the notices in this file, not extracted game geometry, textures, disc files, BIOS, screenshots, RAM dumps or savestates. Each runner imports their own supported game locally. The game-art portrait described below is retained only in the original local workspace; it is excluded from runner builds, which use the neutral-circle fallback. PyInstaller is an optional build-only tool, not a Python dependency of the source runtime; standalone builds also carry the bundled interpreter/runtime's applicable licenses.

## Dan marker image

`web/dan.png` is the unmodified 98 × 98 PNG supplied locally by the user, from [Gallowpedia’s MediEvil Rolling Demo life-model image](https://medievil.wiki/images/thumb/3/39/MediEvilRollingDemo-LifeModel.png/98px-MediEvilRollingDemo-LifeModel.png). The browser uses this local copy; it does not contact the wiki. It is game artwork, not covered by FrogLord’s MIT license. No redistribution rights are asserted.

## Emulator and investigation tools

- [PCSX-Redux](https://github.com/grumpycoders/pcsx-redux), local ARM build `1525a93676dbece9fe70f10ff129aeaa14eec30d`. Runtime shared-memory and Lua research API references came from its source. It is a separate GPL-licensed emulator; preserve its own license/source obligations if redistributing it.
- [REA agents](https://www.npmjs.com/package/rea-agents) 6.5.0 and Ghidra 12.1.3 were used for scalar reverse engineering.
- [majbal87/rea-addons](https://github.com/majbal87/rea-addons), revision `e64abff9a4f21cc0a5b603bcdf90233ca818b706`: PS-X EXE-to-ELF wrapper. The attempted PSX language integration was not used by the successful REA analysis.
- [MediEvil community decompilation](https://github.com/MediEvilDecompilation/medievil-decomp) and [SirDarcanos/MediEvil](https://github.com/SirDarcanos/MediEvil) supplied investigation leads; fixed-address coordinate lists were not adopted as runtime truth.

Tools are under `../tools/` and references under `../reference/`, each retaining their own upstream notices. The map server itself uses Python’s standard library and browser APIs, with no third-party runtime packages.

MediEvil, its disc contents, extracted geometry, BIOS, screenshots and memory/state dumps remain subject to their respective owners’ rights. This local setup does not grant permission to redistribute those assets. No game assets are fetched by the map server.
