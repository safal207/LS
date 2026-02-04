import psutil
import logging
from config import MAX_RAM_USAGE_MB

logger = logging.getLogger(__name__)

def check_system_resources() -> bool:
    """
    Check if system has sufficient resources to run the application
    Returns True if resources are adequate, False otherwise
    """
    try:
        # Check available RAM
        memory = psutil.virtual_memory()
        available_mb = memory.available / (1024 * 1024)
        
        logger.info(f"Available RAM: {available_mb:.1f} MB")
        logger.info(f"Required RAM: {MAX_RAM_USAGE_MB} MB")
        
        if available_mb < MAX_RAM_USAGE_MB * 1.5:  # 1.5x buffer
            logger.warning(f"Low available RAM: {available_mb:.1f} MB")
            return False
            
        # Check CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        logger.info(f"Current CPU usage: {cpu_percent}%")
        
        if cpu_percent > 80:
            logger.warning(f"High CPU usage: {cpu_percent}%")
            return False
            
        logger.info("System resources check passed")
        return True
        
    except Exception as e:
        logger.error(f"Error checking system resources: {e}")
        return False

def format_latency(start_time: float, end_time: float) -> str:
    """Format latency measurement for logging"""
    latency = end_time - start_time
    return f"{latency:.2f}s"

def is_question(text: str) -> bool:
    """
    Simple heuristic to detect if text is a question
    Based on question marks and keywords
    """
    text_lower = text.lower().strip()
    
    # Check for question mark
    if '?' in text:
        return True
    
    # Check for question keywords
    from config import QUESTION_KEYWORDS
    for keyword in QUESTION_KEYWORDS:
        if keyword in text_lower:
            return True
    
    # Additional patterns for common question phrases
    question_patterns = [
        "tell me", "explain", "describe", "what", "how", "why",
        "can you", "could you", "would you", "please",
        "расскажи", "объясни", "опиши", "что", "как", "почему",
        "можешь", "мог бы", "расскажите", "объясните"
    ]
    
    for pattern in question_patterns:
        if pattern in text_lower:
            return True
    
    return False