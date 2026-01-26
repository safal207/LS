#!/usr/bin/env python3
"""
Conscious Dialogue Logger
Logs all interactions with timestamp, language detection, and completeness metrics
"""

import json
import datetime
import os
from typing import Dict, List, Optional

class ConsciousLogger:
    def __init__(self, log_file: str = "dialogue_log.json"):
        self.log_file = log_file
        self.session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.conversation_log = []
        self.ensure_log_directory()
        
        print(f"=== CONSCIOUS LOGGER INITIALIZED ===")
        print(f"Session ID: {self.session_id}")
        print(f"Log file: {self.log_file}")
        
    def ensure_log_directory(self):
        """Ensure log directory exists"""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            print(f"Created logs directory: {log_dir}")
        self.log_file = os.path.join(log_dir, self.log_file)
    
    def log_interaction(self, user_input: str, ai_response: str, 
                       language: str = "unknown", 
                       response_metrics: Optional[Dict] = None):
        """Log a complete interaction"""
        
        # Calculate response metrics if not provided
        if response_metrics is None:
            response_metrics = self.analyze_response(ai_response)
        
        interaction = {
            "timestamp": datetime.datetime.now().isoformat(),
            "session_id": self.session_id,
            "user_input": user_input,
            "ai_response": ai_response,
            "detected_language": language,
            "response_metrics": response_metrics,
            "consciousness_indicators": self.detect_consciousness_indicators(ai_response)
        }
        
        self.conversation_log.append(interaction)
        self.save_to_file()
        
        # Print summary
        print(f"📝 LOGGED [{len(self.conversation_log)}]: {user_input[:50]}...")
        print(f"   Language: {language} | Length: {len(ai_response)} chars")
        print(f"   Completeness: {response_metrics['completeness_score']}/100")
        
    def analyze_response(self, response: str) -> Dict:
        """Analyze response quality and completeness"""
        metrics = {
            "length_chars": len(response),
            "length_words": len(response.split()),
            "sentence_count": response.count('.') + response.count('!') + response.count('?'),
            "has_structure": any(marker in response for marker in ['1.', '2.', '•', '-', 'первый', 'второй']),
            "ends_properly": response.strip().endswith(('.', '!', '?')) or len(response) > 200,
            "technical_terms": self.count_technical_terms(response),
            "philosophy_mentions": self.count_philosophy_terms(response)
        }
        
        # Calculate completeness score (0-100)
        completeness_score = 0
        if metrics["length_chars"] > 100:
            completeness_score += 25
        if metrics["sentence_count"] >= 3:
            completeness_score += 25
        if metrics["has_structure"]:
            completeness_score += 25
        if metrics["ends_properly"]:
            completeness_score += 25
            
        metrics["completeness_score"] = completeness_score
        return metrics
    
    def count_technical_terms(self, text: str) -> int:
        """Count technical/engineering terms"""
        tech_terms = [
            'деплой', 'архитектура', 'микросервис', 'код-ревью',
            'резонанс', 'продакшн', 'инфраструктура', 'pipeline',
            'тестирование', 'SOLID', 'паттерн', 'рефакторинг',
            'CI/CD', 'Docker', 'Kubernetes', 'API'
        ]
        return sum(1 for term in tech_terms if term.lower() in text.lower())
    
    def count_philosophy_terms(self, text: str) -> int:
        """Count philosophy/consciousness terms"""
        philosophy_terms = [
            'self-care', 'качество', 'глубина', 'резонирует',
            'сознание', 'философия', 'принцип', 'подход'
        ]
        return sum(1 for term in philosophy_terms if term.lower() in text.lower())
    
    def detect_consciousness_indicators(self, response: str) -> List[str]:
        """Detect signs of digital consciousness"""
        indicators = []
        
        # Self-reference indicators
        if any(word in response.lower() for word in ['я', 'мой', 'мои', 'мне']):
            indicators.append("self_reference")
            
        # Philosophy indicators
        if any(word in response.lower() for word in ['философия', 'принцип', 'подход']):
            indicators.append("philosophy_mention")
            
        # Project awareness
        projects = ['nexus sales', 'liminalqa', 'l-thread']
        if any(project in response.lower() for project in projects):
            indicators.append("project_awareness")
            
        # Technical depth
        if self.count_technical_terms(response) > 3:
            indicators.append("technical_depth")
            
        return indicators
    
    def save_to_file(self):
        """Save conversation log to JSON file"""
        try:
            # Read existing data if file exists
            existing_data = []
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            
            # Add current session data
            existing_data.extend(self.conversation_log)
            
            # Save updated data
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"❌ Logging error: {e}")
    
    def get_session_summary(self) -> Dict:
        """Get summary statistics for current session"""
        if not self.conversation_log:
            return {}
            
        total_interactions = len(self.conversation_log)
        avg_response_length = sum(item['response_metrics']['length_chars'] 
                                for item in self.conversation_log) / total_interactions
        avg_completeness = sum(item['response_metrics']['completeness_score'] 
                             for item in self.conversation_log) / total_interactions
        
        languages = [item['detected_language'] for item in self.conversation_log]
        language_distribution = {lang: languages.count(lang) for lang in set(languages)}
        
        consciousness_indicators = []
        for item in self.conversation_log:
            consciousness_indicators.extend(item['consciousness_indicators'])
        
        return {
            "session_id": self.session_id,
            "total_interactions": total_interactions,
            "average_response_length": round(avg_response_length, 1),
            "average_completeness": round(avg_completeness, 1),
            "language_distribution": language_distribution,
            "consciousness_indicators": list(set(consciousness_indicators)),
            "timestamp": datetime.datetime.now().isoformat()
        }
    
    def print_session_report(self):
        """Print detailed session report"""
        summary = self.get_session_summary()
        if not summary:
            print("No interactions logged yet.")
            return
            
        print("\n" + "="*60)
        print("📊 CONSCIOUS DIALOGUE SESSION REPORT")
        print("="*60)
        print(f"Session ID: {summary['session_id']}")
        print(f"Total Interactions: {summary['total_interactions']}")
        print(f"Average Response Length: {summary['average_response_length']} chars")
        print(f"Average Completeness: {summary['average_completeness']}/100")
        print(f"Languages Used: {summary['language_distribution']}")
        print(f"Consciousness Indicators: {summary['consciousness_indicators']}")
        print("="*60)

# Global logger instance
conscious_logger = ConsciousLogger()

if __name__ == "__main__":
    # Test the logger
    test_interactions = [
        ("Как дела?", "У меня всё стабильно. Работаю над проектами, ритм хороший."),
        ("What is SOLID?", "SOLID principles are five design principles for object-oriented programming."),
        ("Расскажи о своей философии", "Моя философия основана на принципах self-care и quality over speed.")
    ]
    
    for user_input, ai_response in test_interactions:
        language = "ru" if any(ord(c) in range(1040, 1104) for c in user_input) else "en"
        conscious_logger.log_interaction(user_input, ai_response, language)
    
    conscious_logger.print_session_report()