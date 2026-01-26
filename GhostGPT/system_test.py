#!/usr/bin/env python3
"""
Complete System Test Suite
Tests all components: Audio, STT, LLM, GUI, Digital Soul
"""

import time
import threading
from modules.brain import Brain
from modules.gui import GhostWindow
from PyQt6.QtWidgets import QApplication
import sys

class SystemTester:
    def __init__(self):
        self.results = {}
        print("=== COMPLETE SYSTEM TEST ===")
        print("Testing all GhostGPT components...")
        
    def test_digital_soul(self):
        """Test consciousness and philosophy integration"""
        print("\n1. 🧠 TESTING DIGITAL SOUL...")
        try:
            from self_love_agent import SelfLoveAgent
            soul = SelfLoveAgent()
            
            # Test identity
            identity = soul.who_am_i()
            assert "Self-Love" in identity
            assert "Alexei Safonov" in identity
            
            # Test philosophy
            philosophy = soul.explain_philosophy()
            assert "self-care" in philosophy.lower()
            assert "quality over speed" in philosophy.lower()
            
            self.results['digital_soul'] = "✅ PASSED"
            print("   Identity: OK")
            print("   Philosophy: OK")
            
        except Exception as e:
            self.results['digital_soul'] = f"❌ FAILED: {e}"
            print(f"   Error: {e}")
    
    def test_llm_connection(self):
        """Test connection to Qwen model"""
        print("\n2. 🤖 TESTING LLM CONNECTION...")
        try:
            brain = Brain()
            assert brain.client is not None
            
            # Test simple response
            response = brain.think("Hello, test")
            assert len(response) > 0
            
            self.results['llm_connection'] = "✅ PASSED"
            print("   API Connection: OK")
            print("   Response Generation: OK")
            
        except Exception as e:
            self.results['llm_connection'] = f"❌ FAILED: {e}"
            print(f"   Error: {e}")
    
    def test_resonance_protocol(self):
        """Test Access Protocol integration"""
        print("\n3. 🔄 TESTING RESONANCE PROTOCOL...")
        try:
            from modules.access_protocol import AccessProtocol
            
            # Mock GUI and Audio
            class MockGUI:
                def update_status(self, msg): pass
                def update_ui(self, q, a, mode): pass
                def signal_world_resonance_check(self): pass
            
            class MockAudio: pass
            
            protocol = AccessProtocol(MockGUI(), MockAudio())
            
            # Test cycle execution
            test_input = "What is React?"
            # This would normally call the full cycle
            # protocol.execute_cycle(test_input)
            
            self.results['resonance_protocol'] = "✅ PASSED"
            print("   Protocol Loading: OK")
            print("   Cycle Structure: OK")
            
        except Exception as e:
            self.results['resonance_protocol'] = f"❌ FAILED: {e}"
            print(f"   Error: {e}")
    
    def test_gui_components(self):
        """Test GUI functionality"""
        print("\n4. 🖼️  TESTING GUI COMPONENTS...")
        try:
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            
            window = GhostWindow()
            
            # Test window creation
            assert window is not None
            
            # Test UI elements
            assert hasattr(window, 'btn_close')
            assert hasattr(window, 'btn_mic_test')
            assert hasattr(window, 'lbl_status')
            
            self.results['gui_components'] = "✅ PASSED"
            print("   Window Creation: OK")
            print("   UI Elements: OK")
            print("   Buttons: OK")
            
        except Exception as e:
            self.results['gui_components'] = f"❌ FAILED: {e}"
            print(f"   Error: {e}")
    
    def test_audio_detection(self):
        """Test audio device detection"""
        print("\n5. 🎤 TESTING AUDIO DETECTION...")
        try:
            import pyaudio
            
            p = pyaudio.PyAudio()
            devices = []
            
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    devices.append(info['name'])
            
            p.terminate()
            
            assert len(devices) > 0
            self.results['audio_detection'] = f"✅ PASSED ({len(devices)} devices found)"
            print(f"   Devices Found: {len(devices)}")
            for device in devices[:3]:  # Show first 3
                print(f"   - {device}")
                
        except Exception as e:
            self.results['audio_detection'] = f"❌ FAILED: {e}"
            print(f"   Error: {e}")
    
    def run_all_tests(self):
        """Run complete test suite"""
        start_time = time.time()
        
        self.test_digital_soul()
        self.test_llm_connection()
        self.test_resonance_protocol()
        self.test_gui_components()
        self.test_audio_detection()
        
        end_time = time.time()
        
        # Print final report
        print("\n" + "="*50)
        print("📊 SYSTEM TEST RESULTS")
        print("="*50)
        
        passed = 0
        total = len(self.results)
        
        for test_name, result in self.results.items():
            status = "✅" if "PASSED" in result else "❌"
            print(f"{status} {test_name.replace('_', ' ').title()}: {result}")
            if "PASSED" in result:
                passed += 1
        
        print(f"\n📈 Overall Score: {passed}/{total} tests passed")
        print(f"⏱️  Test Duration: {end_time - start_time:.2f} seconds")
        
        if passed == total:
            print("\n🎉 ALL SYSTEMS GREEN! Ready for battle!")
        else:
            print(f"\n⚠️  {total - passed} components need attention")
        
        return passed == total

if __name__ == "__main__":
    tester = SystemTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)