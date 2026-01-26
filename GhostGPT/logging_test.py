#!/usr/bin/env python3
"""
Conscious Logging Test with Truncation Detection
Tests the dialogue logging system and verifies complete response display
"""

from modules.brain import Brain
from conscious_logger import conscious_logger
import time

class ConsciousLoggingTest:
    def __init__(self):
        self.brain = Brain()
        print("=== CONSCIOUS LOGGING TEST WITH TRUNCATION DETECTION ===")
        print("Testing dialogue logging and complete response display...")
        
    def check_truncation(self, text):
        """Enhanced truncation detection"""
        text = text.strip()
        
        # Check for proper ending punctuation
        proper_endings = ('.', '!', '?', '}', '>', '"', ')', ']')
        has_proper_ending = text.endswith(proper_endings)
        
        # Check for truncation indicators
        truncation_patterns = [
            '...', 'продолжение', 'далее', 'и т.д.', 'и так далее',
            'more...', '(continued)', '[truncated]', 'etc.'
        ]
        has_truncation_indicator = any(pattern in text.lower() for pattern in truncation_patterns)
        
        # Check if ends mid-word (single letter at end)
        words = text.split()
        if words and len(words[-1]) == 1 and words[-1].isalpha():
            return "❌ TRUNCATED (Ends mid-word)"
        
        # Check for incomplete sentences
        if not has_proper_ending and len(text) > 100:
            # If long text doesn't end properly, likely truncated
            return "⚠️ SUSPECTED TRUNCATION (No proper ending)"
        
        if has_truncation_indicator:
            return "❌ CONFIRMED TRUNCATION (Indicator found)"
            
        if has_proper_ending:
            return "✅ COMPLETE (Proper ending)"
        
        return "✅ COMPLETE (Short text acceptable)"
        
    def test_logging_and_display(self):
        """Test that responses are logged and displayed completely"""
        
        test_dialogues = [
            {
                "question": "Какие виды тестирования ПО существуют?",
                "expected_length": 800,
                "language": "ru"
            },
            {
                "question": "What is the Observer design pattern?",
                "expected_length": 600,
                "language": "en"
            },
            {
                "question": "Расскажи о своей философии программирования",
                "expected_length": 1200,  # Increased expectation
                "language": "ru"
            }
        ]
        
        print("\n" + "="*70)
        print("CONSCIOUS DIALOGUE TESTING WITH TRUNCATION DETECTION")
        print("="*70)
        
        for i, dialogue in enumerate(test_dialogues, 1):
            question = dialogue["question"]
            expected_length = dialogue["expected_length"]
            language = dialogue["language"]
            
            print(f"\n[{i}] {language.upper()} DIALOGUE TEST")
            print(f"Question: {question}")
            print("-" * 60)
            
            # Get response
            response = self.brain.think(question)
            
            # Log consciously
            conscious_logger.log_interaction(
                user_input=question,
                ai_response=response,
                language=language
            )
            
            # Enhanced analysis
            print(f"Response Length: {len(response)} characters")
            print(f"Expected Minimum: {expected_length} characters")
            print(f"Length Status: {'✅ GOOD' if len(response) >= expected_length else '⚠️  SHORT'}")
            
            # Truncation check
            truncation_status = self.check_truncation(response)
            print(f"Truncation Check: {truncation_status}")
            
            # Show beginning and end to verify completeness
            if len(response) > 200:
                print(f"Beginning: {response[:100]}...")
                print(f"Ending: ...{response[-100:]}")
                
                # Special check for the ending
                ending_text = response[-50:]
                print(f"Final 50 chars: '{ending_text}'")
            else:
                print(f"Full Response: {response}")
            
            print("="*60)
            time.sleep(1)
        
        # Test interface display simulation with long response
        print("\n" + "="*70)
        print("LONG RESPONSE TEST")
        print("="*70)
        
        long_question = "Расскажи подробно о принципах SOLID, приведи примеры на Python и объясни, почему каждый принцип важен для проектирования качественного кода"
        long_response = self.brain.think(long_question)
        
        print(f"Long Question: {long_question}")
        print(f"Response Length: {len(long_response)} characters")
        print(f"Truncation Status: {self.check_truncation(long_response)}")
        
        if len(long_response) > 1000:
            preview = long_response[:800] + "..."
            print("Interface would show preview + 'Full answer saved in logs'")
            print(f"Preview length: {len(preview)} characters")
        else:
            print("Interface would show complete response")
            print(f"Complete length: {len(long_response)} characters")
        
        print("="*70)
    
    def show_log_analysis(self):
        """Show analysis of logged conversations"""
        print("\n" + "="*70)
        print("LOG ANALYSIS")
        print("="*70)
        
        summary = conscious_logger.get_session_summary()
        
        if summary:
            print(f"Session ID: {summary['session_id']}")
            print(f"Total Dialogues: {summary['total_interactions']}")
            print(f"Average Response Length: {summary['average_response_length']} chars")
            print(f"Average Completeness Score: {summary['average_completeness']}/100")
            print(f"Languages Used: {summary['language_distribution']}")
            print(f"Consciousness Indicators: {summary['consciousness_indicators']}")
        else:
            print("No interactions logged in this session")
        
        print("="*70)

if __name__ == "__main__":
    tester = ConsciousLoggingTest()
    tester.test_logging_and_display()
    tester.show_log_analysis()
    
    print("\n" + "="*70)
    print("🎯 CONSCIOUS LOGGING TEST COMPLETE")
    print("All dialogues are being tracked with full metadata!")
    print("Enhanced truncation detection is active!")
    print("="*70)