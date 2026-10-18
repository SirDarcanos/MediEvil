import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from disc_import import Disc, image_path, import_game, load_manifest


def record(name, sector, size, directory=False):
    name = name if isinstance(name, bytes) else name.encode('ascii')
    out = bytearray(33 + len(name) + (len(name) % 2 == 0))
    out[0] = len(out); out[2:6] = sector.to_bytes(4, 'little')
    out[10:14] = size.to_bytes(4, 'little'); out[25] = 2 if directory else 0
    out[32] = len(name); out[33:33+len(name)] = name
    return out


def fixture(path, raw=False, payload=b'hello'):
    sectors = [bytearray(2048) for _ in range(24)]
    pvd = sectors[16]; pvd[:7] = b'\x01CD001\x01';struct.pack_into('<H', pvd, 128, 2048)
    pvd[156:190] = record(b'\0', 20, 2048, True)
    directory = record('EXAMPLE.BIN;1', 21, len(payload))
    sectors[20][:len(directory)] = directory
    sectors[21][:len(payload)] = payload
    if raw:
        path.write_bytes(b''.join(bytes(24)+s+bytes(280)for s in sectors))
    else:path.write_bytes(b''.join(sectors))


class DiscTests(unittest.TestCase):
    def test_iso_and_mode2_raw_read_same_bytes_without_modifying_source(self):
        with tempfile.TemporaryDirectory()as tmp:
            for raw in (False, True):
                p=Path(tmp)/str(raw);fixture(p, raw)
                before=p.read_bytes();d=Disc(p)
                try:
                    entries=d.directory(d.root)
                    self.assertEqual(b''.join(d.chunks(entries['EXAMPLE.BIN'])), b'hello')
                    d.copy(entries['EXAMPLE.BIN'], Path(tmp)/('copy'+str(raw)))
                finally:d.close()
                self.assertEqual(before,p.read_bytes())

    def test_cue_resolves_data_track_but_rejects_escape(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'game.cue'
            p.write_text('FILE "Track 1.bin" BINARY\n TRACK 01 MODE2/2352\n INDEX 01 00:00:00\n')
            self.assertEqual(image_path(p),(Path(tmp)/'Track 1.bin').resolve())
            p.write_text('FILE "../private.bin" BINARY\n TRACK 01 MODE2/2352\n')
            with self.assertRaises(ValueError):image_path(p)

    def test_record_rejects_traversal_and_multi_extent(self):
        with self.assertRaises(ValueError):Disc.record(record('../SECRET',1,1))
        bad=record('OK',1,1);bad[25]=128
        with self.assertRaises(ValueError):Disc.record(bad)

    def test_truncated_extent_rejected(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'disc.iso';fixture(p);d=Disc(p)
            try:
                with self.assertRaises(ValueError):list(d.chunks({'sector':999,'size':20}))
            finally:d.close()

    def test_failed_import_never_publishes_partial_cache(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'disc.iso';fixture(p);cache=Path(tmp)/'cache'
            with self.assertRaisesRegex(ValueError,'Required MediEvil'):import_game(p,cache)
            self.assertFalse((cache/'maps').exists())
            self.assertEqual(list(cache.iterdir()),[])

    def test_retail_root_layout_reaches_revision_check_and_cleans_work(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'disc.iso';fixture(p)
            data=bytearray(p.read_bytes())
            records=record('MEDIEVIL.EXE;1',21,5)+record('MEDRES.MWD;1',22,5)+record('OVERLAYS',23,2048,True)
            data[20*2048:21*2048]=records+bytes(2048-len(records));p.write_bytes(data)
            before=p.read_bytes();cache=Path(tmp)/'cache'
            with self.assertRaisesRegex(ValueError,'Unsupported game revision'):import_game(p,cache)
            self.assertEqual(before,p.read_bytes());self.assertEqual(list(cache.iterdir()),[])

    def test_manifest_rejects_external_paths(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp);(p/'manifest.json').write_text(json.dumps({'exe_sha1':'wrong','maps':[]}))
            with self.assertRaises(ValueError):load_manifest(p)
            from disc_import import EXE_SHA1
            maps=[{'code':f'M{n:02}','file':f'M{n:02}.json'}for n in range(25)]
            for row in maps:(p/row['file']).write_text('{}')
            maps[0]['file']='../private.json'
            (p/'manifest.json').write_text(json.dumps({'exe_sha1':EXE_SHA1,'maps':maps}))
            with self.assertRaisesRegex(ValueError,'invalid or missing'):load_manifest(p)

if __name__=='__main__':unittest.main()
