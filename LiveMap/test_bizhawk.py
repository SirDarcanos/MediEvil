"""Synthetic bridge, lifecycle and Windows ABI checks; not native BizHawk evidence."""
import struct
import unittest
import http.client
import threading
from http.server import ThreadingHTTPServer
import app
from unittest.mock import patch
import bizhawk
import emulator_memory
import ram
from test_minimap import fixture, FakeRAM
import test_emulator_memory


def packet(sequence=2, stamp=1000, status=1, data=None):
    data = fixture() if data is None else data
    ranges = [(0x21ca4,32),(0x485ec,32),(0x99ad0,32),(0xeee24,80),(0xedb3c,4),
              (0x100530,4),(0x110024,12),(0x110080,4),(0x120030,12)]
    payload = bytearray(bizhawk.HEADER.pack(b'MLBH',1,sequence,stamp,status,len(ranges),0,0))
    for address,length in ranges:
        payload += struct.pack('<II',address,length)+data[address:address+length]
    return bytes(payload).ljust(bizhawk.PACKET_SIZE,b'\0')


class BridgePacketExamples(unittest.TestCase):
    def test_sparse_export_uses_the_normal_signed_usa_decoder(self):
        raw,paused,seq=bizhawk.decode_packet(packet(),1000.5)
        decoded=ram.decode_snapshot(raw)
        self.assertEqual(decoded['position'],[-32000,-200000,32000])
        self.assertEqual(decoded['physics_position'],[123,-456,789])
        self.assertFalse(paused);self.assertEqual(seq,2)

    def test_wrong_revision_remains_hidden_by_shared_decoder(self):
        raw,_,_=bizhawk.decode_packet(packet(data=bytes(ram.RAM_SIZE)),1000)
        self.assertEqual(ram.decode_snapshot(raw)['status'],'waiting_game')

    def test_inactive_stale_and_future_exports_are_hidden(self):
        for p,t in [(packet(status=0),1000),(packet(stamp=997),1000),(packet(stamp=1002),1000)]:
            with self.assertRaises(OSError):bizhawk.decode_packet(p,t)

    def test_busy_malformed_and_out_of_range_packets_fail_closed(self):
        cases=[packet(sequence=3),b'bad',b'BAD!'+packet()[4:]]
        for address,length in [(0x200000,1),(1,0),(0,0xffffffff)]:
            p=bytearray(packet());struct.pack_into('<II',p,32,address,length);cases.append(p)
        p=bytearray(packet());p[-1]=1;cases.append(p)
        p=bytearray(packet());struct.pack_into('<I',p,20,17);cases.append(p)
        # Second segment overlaps the first.
        p=bytearray(packet());struct.pack_into('<I',p,32+8+32,0x21ca4);cases.append(p)
        for p in cases:
            with self.subTest(size=len(p)):
                with self.assertRaises(ValueError):bizhawk.decode_packet(p,1000)


class Mapping:
    def __init__(self,*args,**kwargs):self.view=packet();self.closed=False
    def close(self):self.closed=True


class BridgeReaderExamples(unittest.TestCase):
    def setUp(self):
        for p in [patch('bizhawk.sys.platform','win32'),patch('bizhawk.ReadOnlyMapping',Mapping),patch('bizhawk.emulator_pids',return_value=[73]),
                  patch('bizhawk.time.time',return_value=1000),patch('bizhawk.time.monotonic',return_value=10)]:
            p.start();self.addCleanup(p.stop)

    def test_waits_for_producer_advance_and_preserves_pause_heartbeat(self):
        reader=bizhawk.BizHawkRAM(73)
        self.assertIsNone(reader.snapshot())
        self.assertIsNone(reader.snapshot())
        reader.mapping.view=packet(sequence=4,status=2)
        self.assertIsNotNone(reader.snapshot());self.assertTrue(reader.is_paused)
        reader.mapping.view=packet(sequence=6,status=2)
        self.assertIsNotNone(reader.snapshot())
        reader.close();self.assertTrue(reader.mapping.closed)

    def test_stopped_or_orphan_export_is_not_a_permanent_paused_marker(self):
        reader=bizhawk.BizHawkRAM(73);self.assertIsNone(reader.snapshot())
        reader.mapping.view=packet(sequence=4);self.assertIsNotNone(reader.snapshot())
        with patch('bizhawk.time.monotonic',return_value=12):
            with self.assertRaises(OSError):reader.snapshot()
        reader.mapping.view=packet(sequence=6,status=0)
        with self.assertRaises(OSError):reader.snapshot()

    def test_busy_or_torn_mapping_is_not_decoded(self):
        reader=bizhawk.BizHawkRAM(73);reader.mapping.view=packet(sequence=3)
        self.assertIsNone(reader.snapshot())
        class Racing:
            n=0
            def __getitem__(self,key):
                self.n+=2
                return packet(sequence=self.n)[key]
        reader.mapping.view=Racing();self.assertIsNone(reader.snapshot())

    def test_new_or_replaced_producer_is_rejected_between_discovery_cycles(self):
        reader=bizhawk.BizHawkRAM(73);reader.snapshot();reader.mapping.view=packet(sequence=4)
        for pids in [[],[74],[73,74]]:
            with patch('bizhawk.emulator_pids',return_value=pids):
                with self.assertRaises(OSError):reader.snapshot()
        # Also catch a second producer that appears during a coherent copy.
        with patch('bizhawk.emulator_pids',side_effect=[[73],[73,74]]):
            with self.assertRaises(OSError):reader.snapshot()

    def test_windows_mapping_requests_only_existing_512_readonly_bytes(self):
        api=test_emulator_memory.WindowsMappingExamples.API()
        with patch('emulator_memory.windows_api',return_value=api):
            m=emulator_memory.ReadOnlyMapping(bizhawk.MAPPING_NAME,size=512)
            self.assertEqual(api.calls[:2],[('open',(4,False,bizhawk.MAPPING_NAME)),('map',(41,4,0,0,512))])
            self.assertEqual(len(m.view),512);self.assertTrue(m.view.readonly);m.close()


class TrackerExamples(unittest.TestCase):
    def setUp(self):
        for p in [patch('ram.sys.platform','win32'),patch('ram.redux_pids',return_value=[]),
                  patch('ram.duckstation_pids',return_value=[]),patch('ram.bizhawk_pids',return_value=[73]),
                  patch('bizhawk.BizHawkRAM',FakeRAM)]:
            p.start();self.addCleanup(p.stop)

    def test_auto_and_explicit_selection_use_bizhawk(self):
        for selected in ['auto','bizhawk']:
            tracker=ram.Tracker(emulator=selected);s=tracker.sample();tracker.close()
            self.assertEqual(s['emulator'],'bizhawk');self.assertEqual(s['position'],[-32000,-200000,32000])

    def test_multiple_instances_cannot_be_misbound_even_with_pid(self):
        with patch('ram.bizhawk_pids',return_value=[73,74]),patch('bizhawk.BizHawkRAM')as opened:
            for selected in ['auto','bizhawk']:
                for pid in [None,73]:
                    s=ram.Tracker(pid=pid,emulator=selected).sample()
                    self.assertEqual(s['status'],'multiple');self.assertNotIn('position',s)
            opened.assert_not_called()

    def test_selected_other_backend_pid_survives_multiple_bizhawk_instances(self):
        class Advancing(FakeRAM):
            def __init__(self,pid):super().__init__(pid);self.frame=60
            def snapshot(self):self.frame+=1;return bytes(fixture(frame=self.frame))
        with patch('ram.redux_pids',return_value=[42]),patch('ram.duckstation_pids',return_value=[43]),\
                patch('ram.bizhawk_pids',return_value=[73,74]),patch('ram.SharedRAM',Advancing),patch('ram.DuckStationRAM',Advancing):
            for pid,backend in [(42,'redux'),(43,'duckstation')]:
                with patch('ram.time.monotonic',return_value=100):
                    tracker=ram.Tracker(pid=pid);sample=tracker.sample();reader=tracker.ram
                self.assertEqual(sample['emulator'],backend);self.assertEqual(sample['status'],'live')
                with patch('ram.time.monotonic',return_value=100.5):tracker.sample()
                with patch('ram.time.monotonic',return_value=101.1):sample=tracker.sample()
                self.assertIs(tracker.ram,reader);self.assertEqual(sample['status'],'live');tracker.close()

    def test_mixed_backends_require_selection(self):
        with patch('ram.redux_pids',return_value=[90]):
            self.assertEqual(ram.Tracker().sample()['status'],'multiple')
            self.assertEqual(ram.Tracker(emulator='bizhawk').sample()['emulator'],'bizhawk')

    def test_exporter_pause_is_immediate_and_does_not_force_reopen(self):
        class Paused(FakeRAM):is_paused=True
        with patch('bizhawk.BizHawkRAM',Paused),patch('ram.time.monotonic',return_value=10):
            tracker=ram.Tracker(emulator='bizhawk');s=tracker.sample();first=tracker.ram
            self.assertEqual(s['status'],'paused')
        with patch('ram.time.monotonic',return_value=12):
            s=tracker.sample();self.assertIs(tracker.ram,first);self.assertEqual(s['status'],'paused')
        tracker.close()

    def test_missing_bridge_reports_how_to_load_it(self):
        with patch('bizhawk.BizHawkRAM',side_effect=OSError('missing')):
            s=ram.Tracker(emulator='bizhawk').sample();self.assertEqual(s['status'],'unavailable')
            self.assertIn('Lua Console',s['message']);self.assertNotIn('position',s)

    def test_stopped_export_hides_position_and_retains_backend_guidance(self):
        class Stopped(FakeRAM):
            def snapshot(self):raise OSError('bridge stopped updating')
        with patch('bizhawk.BizHawkRAM',Stopped):
            sample=ram.Tracker(emulator='bizhawk').sample()
            self.assertEqual(sample['status'],'unavailable');self.assertNotIn('position',sample)
            self.assertEqual(sample['emulator'],'bizhawk');self.assertIn('Lua Console',sample['message'])

    def test_non_windows_and_gdb_combination_are_explicit(self):
        with patch('ram.sys.platform','darwin'):
            s=ram.Tracker(emulator='bizhawk').sample();self.assertIn('Windows',s['message'])
        with self.assertRaises(ValueError):ram.Tracker(emulator='bizhawk',gdb_port=2345)


class BridgeHTTPExamples(unittest.TestCase):
    def test_bridge_is_served_readonly_and_keeps_existing_host_restrictions(self):
        class Feed:
            def current(self):return {'status':'connecting'}
        server=ThreadingHTTPServer(('127.0.0.1',0),app.make_handler(Feed(),{'maps':[]}))
        port=server.server_address[1]
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            client=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
            client.request('GET','/bizhawk.lua');response=client.getresponse();body=response.read()
            self.assertEqual(response.status,200);self.assertIn('text/plain',response.getheader('Content-Type'))
            self.assertIn(b'mmfWriteBytes',body);self.assertIn(b'emu.yield()',body)
            client.close();client=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
            client.request('GET','/bizhawk.lua',headers={'Host':'evil.example'});response=client.getresponse()
            self.assertEqual(response.status,403);response.read();client.close()
        finally:server.shutdown();server.server_close();thread.join(timeout=2)


if __name__=='__main__':unittest.main()
