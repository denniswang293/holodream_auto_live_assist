from types import SimpleNamespace
import ctypes

import pytest

import src.windows_runtime as win


class Function:
    def __init__(self,callback):self.callback=callback
    def __call__(self,*args):return self.callback(*args)


@pytest.mark.parametrize('mode',['scan_code','virtual_key'])
def test_windows_packets_include_real_scan_codes_and_release_flag(monkeypatch,mode):
    expected = dict(zip('SDFJKL',[0x1f,0x20,0x21,0x24,0x25,0x26]))
    packets = []
    def send(count,ref,size):
        packet=ref._obj;key=packet.payload.keyboard
        assert count==1 and size==ctypes.sizeof(packet)
        packets.append((packet.type,key.vk,key.scan,key.flags))
        return 1
    api=SimpleNamespace(MapVirtualKeyW=Function(lambda code,kind:expected[chr(code)]),SendInput=Function(send))
    monkeypatch.setattr(win,'user32',lambda:api)
    actuator=win.WindowsActuator(mode)
    for key in 'SDFJKL':actuator.key_down(key);actuator.key_up(key)
    assert len(packets)==12
    for i,key in enumerate('SDFJKL'):
        flag=8 if mode=='scan_code' else 0
        vk=0 if mode=='scan_code' else ord(key)
        assert packets[2*i]==(1,vk,expected[key],flag)
        assert packets[2*i+1]==(1,vk,expected[key],flag|2)
    with pytest.raises(ValueError):actuator.key_down('A')


def test_unmapped_or_failed_input_is_not_reported_as_sent(monkeypatch):
    api=SimpleNamespace(MapVirtualKeyW=Function(lambda *args:0),SendInput=Function(lambda *args:1))
    monkeypatch.setattr(win,'user32',lambda:api)
    with pytest.raises(ValueError):win.WindowsActuator()
    api.MapVirtualKeyW=Function(lambda *args:0x1f)
    api.SendInput=Function(lambda *args:0)
    actuator=win.WindowsActuator()
    with pytest.raises(OSError):actuator.key_down('S')
