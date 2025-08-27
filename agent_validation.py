#!/usr/bin/env python3
"""
Multi-Agent Content Validation Pipeline
Designed for graceful degradation - NEVER block publication
"""

import os
import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import time
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationResult(Enum):
    PASS = "pass"
    WARNING = "warning"  # Issues found but auto-fixed
    FAIL = "fail"       # Critical issues, but still publish with fallbacks

@dataclass
class AgentResult:
    agent_name: str
    result: ValidationResult
    message: str
    fixes_applied: List[str] = None
    confidence: float = 1.0
    processing_time: float = 0.0
    
    def __post_init__(self):
        if self.fixes_applied is None:
            self.fixes_applied = []

class ContentValidationPipeline:
    """
    Multi-agent validation pipeline with graceful degradation.
    Philosophy: Always publish something, continuously improve quality.
    """
    
    def __init__(self, enable_agents: bool = None, agent_percentage: int = None):
        self.enable_agents = enable_agents if enable_agents is not None else self._should_enable_agents()
        self.agent_percentage = agent_percentage if agent_percentage is not None else int(os.getenv('AGENT_VALIDATION_PERCENTAGE', '0'))
        self.circuit_breaker_failures = 0
        self.max_circuit_breaker_failures = 3
        self.shadow_mode = os.getenv('AGENT_SHADOW_MODE', 'false').lower() == 'true'
        
        logger.info(f"Agent Pipeline: enabled={self.enable_agents}, percentage={self.agent_percentage}%, shadow={self.shadow_mode}")
        
    def _should_enable_agents(self) -> bool:
        """Check if agents should be enabled based on environment"""
        return os.getenv('ENABLE_AGENT_VALIDATION', 'false').lower() == 'true'
    
    def should_use_agents_for_content(self, content_identifier: str) -> bool:
        """Determine if this specific content should go through agent pipeline"""
        if not self.enable_agents:
            return False
        if self.circuit_breaker_failures >= self.max_circuit_breaker_failures:
            logger.warning("Circuit breaker OPEN - agents disabled due to failures")
            return False
        
        # Simple hash-based percentage routing for consistent behavior
        import hashlib
        hash_val = int(hashlib.md5(content_identifier.encode()).hexdigest()[:8], 16)
        return (hash_val % 100) < self.agent_percentage
    
    def validate_content(self, content_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main validation pipeline entry point.
        Returns enhanced content data with validation results.
        """
        start_time = time.time()
        validation_log = []
        
        try:
            if not self.should_use_agents_for_content(content_data.get('url', 'unknown')):
                return self._add_validation_metadata(content_data, [], "agents_disabled")
            
            # Run sequential agent pipeline
            agents = [
                self._extraction_validation_agent,
                self._editorial_validation_agent, 
                self._preview_generation_agent,
                self._publisher_validation_agent
            ]
            
            for agent in agents:
                try:
                    result = agent(content_data)
                    validation_log.append(result)
                    
                    # Apply fixes if any
                    if result.fixes_applied:
                        logger.info(f"{result.agent_name}: Applied fixes: {result.fixes_applied}")
                        
                    # Critical failure handling
                    if result.result == ValidationResult.FAIL:
                        logger.warning(f"{result.agent_name}: FAILED - {result.message}")
                        self.circuit_breaker_failures += 1
                        break
                        
                except Exception as e:
                    logger.error(f"Agent {agent.__name__} crashed: {e}")
                    validation_log.append(AgentResult(
                        agent_name=agent.__name__,
                        result=ValidationResult.FAIL,
                        message=f"Agent crashed: {str(e)}",
                        confidence=0.0
                    ))
                    self.circuit_breaker_failures += 1
                    break
            
            # Success - reset circuit breaker
            if validation_log and validation_log[-1].result != ValidationResult.FAIL:
                self.circuit_breaker_failures = 0
                
        except Exception as e:
            logger.error(f"Validation pipeline crashed: {e}")
            validation_log.append(AgentResult(
                agent_name="pipeline",
                result=ValidationResult.FAIL, 
                message=f"Pipeline error: {str(e)}",
                confidence=0.0
            ))
        
        processing_time = time.time() - start_time
        return self._add_validation_metadata(content_data, validation_log, f"completed_in_{processing_time:.2f}s")
    
    def _add_validation_metadata(self, content_data: Dict[str, Any], validation_log: List[AgentResult], status: str) -> Dict[str, Any]:
        """Add validation metadata to content without breaking existing structure"""
        content_data['_agent_validation'] = {
            'enabled': self.enable_agents,
            'shadow_mode': self.shadow_mode,
            'status': status,
            'results': [
                {
                    'agent': r.agent_name,
                    'result': r.result.value,
                    'message': r.message,
                    'fixes': r.fixes_applied,
                    'confidence': r.confidence,
                    'time': r.processing_time
                } for r in validation_log
            ],
            'overall_confidence': sum(r.confidence for r in validation_log) / len(validation_log) if validation_log else 1.0,
            'circuit_breaker_failures': self.circuit_breaker_failures
        }
        return content_data
    
    # ==================== INDIVIDUAL AGENTS ====================
    
    def _extraction_validation_agent(self, content_data: Dict[str, Any]) -> AgentResult:
        """CRITICAL GATE: Ensures basic content exists and is processable"""
        start_time = time.time()
        fixes = []
        
        # Check if raw data exists and is not empty
        raw_data_path = content_data.get('raw_data_path')
        if not raw_data_path or not Path(raw_data_path).exists():
            return AgentResult(
                agent_name="extraction_agent",
                result=ValidationResult.FAIL,
                message="Raw data file missing - cannot proceed",
                processing_time=time.time() - start_time
            )
        
        # Check if raw data is empty (404 URL case)
        if Path(raw_data_path).stat().st_size == 0:
            return AgentResult(
                agent_name="extraction_agent", 
                result=ValidationResult.FAIL,
                message="Raw data empty - likely 404 URL",
                processing_time=time.time() - start_time
            )
        
        # Check basic transcript structure
        pairs = content_data.get('pairs', [])
        if not pairs or len(pairs) == 0:
            fixes.append("Generated fallback content for empty transcript")
            # Create minimal fallback content
            content_data['pairs'] = [("System", "Content extraction in progress - please check back later.")]
        
        return AgentResult(
            agent_name="extraction_agent",
            result=ValidationResult.PASS if not fixes else ValidationResult.WARNING,
            message="Content extraction validated",
            fixes_applied=fixes,
            processing_time=time.time() - start_time
        )
    
    def _editorial_validation_agent(self, content_data: Dict[str, Any]) -> AgentResult:
        """QUALITY GATE: Fact-checking and format consistency (with auto-fixes)"""
        start_time = time.time()
        fixes = []
        
        # Title format validation and auto-fix
        title = content_data.get('title', '')
        if title and not self._is_standard_title_format(title):
            new_title = self._fix_title_format(title, content_data.get('date'))
            if new_title != title:
                content_data['title'] = new_title
                fixes.append(f"Fixed title format: '{title}' -> '{new_title}'")
        
        # Team assignment validation (placeholder for now - will enhance with MLB API)
        summary = content_data.get('summary', [])
        for i, insight in enumerate(summary):
            if self._has_team_assignment_issue(insight):
                fixed_insight = self._fix_team_assignment(insight)
                if fixed_insight != insight:
                    content_data['summary'][i] = fixed_insight
                    fixes.append(f"Fixed team assignment in insight {i}")
        
        return AgentResult(
            agent_name="editorial_agent",
            result=ValidationResult.WARNING if fixes else ValidationResult.PASS,
            message=f"Editorial validation completed with {len(fixes)} fixes",
            fixes_applied=fixes,
            confidence=0.9 if not fixes else 0.7,
            processing_time=time.time() - start_time
        )
    
    def _preview_generation_agent(self, content_data: Dict[str, Any]) -> AgentResult:
        """ENHANCEMENT GATE: Intelligent preview generation (never blocks)"""
        start_time = time.time()
        fixes = []
        
        preview = content_data.get('preview', '')
        if not preview or self._is_placeholder_preview(preview):
            # Generate better preview from summary
            summary = content_data.get('summary', [])
            new_preview = self._generate_intelligent_preview(summary)
            if new_preview:
                content_data['preview'] = new_preview
                fixes.append("Generated intelligent preview from content")
        
        return AgentResult(
            agent_name="preview_agent",
            result=ValidationResult.WARNING if fixes else ValidationResult.PASS,
            message="Preview generation completed",
            fixes_applied=fixes,
            confidence=0.8,
            processing_time=time.time() - start_time
        )
    
    def _publisher_validation_agent(self, content_data: Dict[str, Any]) -> AgentResult:
        """FINAL GATE: Publication readiness (basic checks only)"""
        start_time = time.time()
        
        # Basic HTML structure validation
        required_fields = ['title', 'summary', 'pairs']
        missing_fields = [field for field in required_fields if not content_data.get(field)]
        
        if missing_fields:
            return AgentResult(
                agent_name="publisher_agent",
                result=ValidationResult.FAIL,
                message=f"Missing required fields: {missing_fields}",
                processing_time=time.time() - start_time
            )
        
        return AgentResult(
            agent_name="publisher_agent", 
            result=ValidationResult.PASS,
            message="Ready for publication",
            confidence=1.0,
            processing_time=time.time() - start_time
        )
    
    # ==================== HELPER METHODS ====================
    
    def _is_standard_title_format(self, title: str) -> bool:
        """Check if title follows 'Chat: MMM DD' or 'Mailbag: MMM DD' format"""
        import re
        pattern = r'^(Chat|Mailbag): [A-Z][a-z]{2} \d{1,2}$'
        return bool(re.match(pattern, title))
    
    def _fix_title_format(self, title: str, date: str = None) -> str:
        """Convert title to standard format"""
        if "chat" in title.lower():
            if date:
                from datetime import datetime
                date_obj = datetime.strptime(str(date), '%Y-%m-%d')
                return f"Chat: {date_obj.strftime('%b %d').replace(' 0', ' ')}"
            return "Chat: Recent"
        elif "mailbag" in title.lower():
            if date:
                from datetime import datetime  
                date_obj = datetime.strptime(str(date), '%Y-%m-%d')
                return f"Mailbag: {date_obj.strftime('%b %d').replace(' 0', ' ')}"
            return "Mailbag: Recent"
        return title  # Return original if can't determine type
    
    def _has_team_assignment_issue(self, insight: str) -> bool:
        """Detect potential team assignment issues (basic heuristics for now)"""
        # Look for known problematic patterns
        problematic_patterns = [
            "Red Sox.*Rice",  # Ben Rice is Yankees, not Red Sox
            "Yankees.*Teel",  # Kyle Teel is Red Sox prospect
        ]
        import re
        return any(re.search(pattern, insight, re.IGNORECASE) for pattern in problematic_patterns)
    
    def _fix_team_assignment(self, insight: str) -> str:
        """Auto-fix known team assignment issues"""
        import re
        
        # Fix Ben Rice team assignment
        if re.search(r'Red Sox.*Ben Rice', insight, re.IGNORECASE):
            insight = re.sub(r'Red Sox.*Ben Rice', "Yankees' Ben Rice", insight, flags=re.IGNORECASE)
        
        # Add more fixes as we discover them
        return insight
    
    def _is_placeholder_preview(self, preview: str) -> bool:
        """Check if preview is a placeholder text"""
        placeholders = [
            "summary generation in progress",
            "click to read the full summary",
            "processing...",
            ""
        ]
        return any(placeholder in preview.lower() for placeholder in placeholders)
    
    def _generate_intelligent_preview(self, summary: List[str]) -> str:
        """Generate meaningful preview from summary insights"""
        if not summary or len(summary) == 0:
            return "Latest MLB discussion and analysis"
        
        # Extract key topics from first few insights
        import re
        topics = []
        
        for insight in summary[:3]:  # First 3 insights
            # Extract player names (First Last format)
            players = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', insight)
            topics.extend(players[:2])  # Max 2 players per insight
            
            # Extract team names
            teams = ['Red Sox', 'Yankees', 'Cubs', 'Dodgers', 'Orioles', 'Rays', 'Phillies', 'Mets']
            for team in teams:
                if team in insight and team not in topics:
                    topics.append(team)
                    break
        
        # Remove duplicates while preserving order
        unique_topics = []
        for topic in topics:
            if topic not in unique_topics:
                unique_topics.append(topic)
        
        if unique_topics:
            return ", ".join(unique_topics[:4])  # Max 4 topics
        
        # Fallback to first insight text (truncated)
        first_insight = summary[0] if summary else ""
        return first_insight[:100] + "..." if len(first_insight) > 100 else first_insight


# Global pipeline instance
_pipeline = None

def get_validation_pipeline() -> ContentValidationPipeline:
    """Get singleton validation pipeline instance"""
    global _pipeline
    if _pipeline is None:
        _pipeline = ContentValidationPipeline()
    return _pipeline

def validate_content(content_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for content validation"""
    pipeline = get_validation_pipeline()
    return pipeline.validate_content(content_data)

# Emergency rollback function
def disable_agents():
    """Emergency function to disable all agent validation"""
    global _pipeline
    if _pipeline:
        _pipeline.enable_agents = False
        _pipeline.circuit_breaker_failures = _pipeline.max_circuit_breaker_failures
    logger.warning("EMERGENCY: All agent validation disabled")