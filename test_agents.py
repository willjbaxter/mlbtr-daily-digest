#!/usr/bin/env python3
"""
Agent validation testing script
Aggressive testing for rapid deployment
"""

import os
import sys
from pathlib import Path
import json
from datetime import datetime

# Test environment configurations
TEST_CONFIGS = {
    "disabled": {
        "ENABLE_AGENT_VALIDATION": "false",
        "AGENT_VALIDATION_PERCENTAGE": "0",
        "AGENT_SHADOW_MODE": "false"
    },
    "shadow": {
        "ENABLE_AGENT_VALIDATION": "true", 
        "AGENT_VALIDATION_PERCENTAGE": "100",
        "AGENT_SHADOW_MODE": "true"
    },
    "canary": {
        "ENABLE_AGENT_VALIDATION": "true",
        "AGENT_VALIDATION_PERCENTAGE": "25", 
        "AGENT_SHADOW_MODE": "false"
    },
    "full": {
        "ENABLE_AGENT_VALIDATION": "true",
        "AGENT_VALIDATION_PERCENTAGE": "100",
        "AGENT_SHADOW_MODE": "false"
    }
}

def set_test_env(config_name: str):
    """Set environment variables for testing"""
    if config_name not in TEST_CONFIGS:
        print(f"Unknown config: {config_name}. Available: {list(TEST_CONFIGS.keys())}")
        return False
    
    config = TEST_CONFIGS[config_name]
    for key, value in config.items():
        os.environ[key] = value
    
    print(f"🔧 Set environment: {config_name}")
    for key, value in config.items():
        print(f"   {key}={value}")
    return True

def test_agent_import():
    """Test that agent system can be imported"""
    print("🧪 Testing agent import...")
    try:
        from agent_validation import validate_content, get_validation_pipeline
        print("✅ Agent system imported successfully")
        return True
    except Exception as e:
        print(f"❌ Agent import failed: {e}")
        return False

def test_existing_content():
    """Test agents against existing content"""
    print("\n🧪 Testing agents against existing content...")
    
    # Test cases - known problematic content
    test_cases = [
        {
            "name": "Aug 15 - Title format issue",
            "path": "out/chat/2025-08-15",
            "expected_fixes": ["title_format"]
        },
        {
            "name": "Aug 21 - Processing failure", 
            "path": "out/chat/2025-08-21",
            "expected_fixes": ["content_extraction"]
        }
    ]
    
    from agent_validation import validate_content
    
    results = []
    for test_case in test_cases:
        print(f"\n  Testing: {test_case['name']}")
        
        # Create mock content data
        content_data = {
            'url': f"https://example.com/{test_case['name']}",
            'title': "Front Office Subscriber Chat Transcript",  # Known bad format
            'summary': ["Summary generation in progress..."],  # Known placeholder
            'pairs': [("Speaker", "Test content")],
            'post_type': 'chat',
            'date': '2025-08-15',
            'raw_data_path': f"{test_case['path']}/raw_extracted_data.txt",
            'preview': "Summary generation in progress..."
        }
        
        try:
            validated = validate_content(content_data)
            validation_info = validated.get('_agent_validation', {})
            
            fixes_applied = []
            for result in validation_info.get('results', []):
                if result.get('fixes'):
                    fixes_applied.extend(result['fixes'])
            
            print(f"    ✅ Validation completed")
            print(f"    🔧 Fixes applied: {len(fixes_applied)}")
            for fix in fixes_applied[:3]:  # Show first 3 fixes
                print(f"       - {fix}")
            
            results.append({
                'test': test_case['name'],
                'success': True,
                'fixes': len(fixes_applied),
                'confidence': validation_info.get('overall_confidence', 0)
            })
            
        except Exception as e:
            print(f"    ❌ Validation failed: {e}")
            results.append({
                'test': test_case['name'], 
                'success': False,
                'error': str(e)
            })
    
    return results

def test_circuit_breaker():
    """Test circuit breaker functionality"""
    print("\n🧪 Testing circuit breaker...")
    
    from agent_validation import get_validation_pipeline
    
    pipeline = get_validation_pipeline()
    initial_failures = pipeline.circuit_breaker_failures
    
    # Simulate failures
    bad_content = {
        'url': 'test://circuit-breaker',
        'title': '',  # Will cause failures
        'summary': [],
        'pairs': [],
        'post_type': 'chat',
        'date': '2025-01-01',
        'raw_data_path': '/nonexistent/path.txt',  # Will cause failure
        'preview': ''
    }
    
    # Run validation multiple times to trigger circuit breaker
    for i in range(5):
        try:
            result = pipeline.validate_content(bad_content.copy())
            validation_info = result.get('_agent_validation', {})
            print(f"  Attempt {i+1}: failures={pipeline.circuit_breaker_failures}")
            
            if pipeline.circuit_breaker_failures >= pipeline.max_circuit_breaker_failures:
                print(f"    🚨 Circuit breaker OPEN after {pipeline.circuit_breaker_failures} failures")
                break
                
        except Exception as e:
            print(f"  Attempt {i+1}: Exception - {e}")
    
    return pipeline.circuit_breaker_failures > initial_failures

def test_performance():
    """Test agent performance impact"""
    print("\n🧪 Testing performance impact...")
    
    import time
    from agent_validation import validate_content
    
    test_content = {
        'url': 'test://performance',
        'title': 'Chat: Aug 27',
        'summary': ["Test insight about Yankees player", "Cubs discussion ongoing"],
        'pairs': [("Steve Adams", "Test response content")],
        'post_type': 'chat',
        'date': '2025-08-27',
        'raw_data_path': '/dev/null',
        'preview': 'Test preview'
    }
    
    # Run multiple validations and measure time
    times = []
    for i in range(5):
        start = time.time()
        validated = validate_content(test_content.copy())
        end = time.time()
        times.append(end - start)
        
        validation_info = validated.get('_agent_validation', {})
        print(f"  Run {i+1}: {(end-start)*1000:.1f}ms, confidence: {validation_info.get('overall_confidence', 0):.2f}")
    
    avg_time = sum(times) / len(times)
    print(f"  📊 Average processing time: {avg_time*1000:.1f}ms")
    
    return avg_time

def run_integration_test():
    """Run with real content processing"""
    print("\n🧪 Running integration test...")
    
    # Test with a working URL (the recent mailbag)
    os.system('ENABLE_AGENT_VALIDATION=true AGENT_VALIDATION_PERCENTAGE=100 GEMINI_API_KEY=AIzaSyC8g4WkbIs5EszcArdPO1Y0CZgxoAXAX4U .venv/bin/python3 mlbtr_daily_summary.py --manual-url "https://www.mlbtraderumors.com/2025/08/mlb-mailbag-kyle-tucker-nick-lodolo-bo-bichette-rays-mets.html" --manual-type mailbag --manual-date 2025-08-27')

def main():
    print("🚀 AGENT VALIDATION TESTING - AGGRESSIVE MODE")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        config = sys.argv[1]
        if not set_test_env(config):
            return
    else:
        print("Usage: python test_agents.py [disabled|shadow|canary|full|integration]")
        return
    
    if sys.argv[1] == "integration":
        run_integration_test()
        return
    
    # Run test suite
    results = {}
    
    # Basic functionality tests
    results['import'] = test_agent_import()
    
    if results['import']:
        results['existing_content'] = test_existing_content()
        results['circuit_breaker'] = test_circuit_breaker()
        results['performance'] = test_performance()
    
    # Summary
    print("\n" + "="*50)
    print("🏁 TEST RESULTS SUMMARY")
    print("="*50)
    
    for test_name, result in results.items():
        if isinstance(result, bool):
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name:20}: {status}")
        elif isinstance(result, list):
            passed = sum(1 for r in result if r.get('success', False))
            total = len(result)
            print(f"{test_name:20}: {passed}/{total} passed")
        elif isinstance(result, float):
            print(f"{test_name:20}: {result*1000:.1f}ms avg")
    
    overall_success = all(
        result is True or (isinstance(result, list) and all(r.get('success', False) for r in result))
        for result in results.values() if isinstance(result, (bool, list))
    )
    
    print(f"\n{'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    if overall_success:
        print("\n🚀 READY FOR DEPLOYMENT!")
        print("Next steps:")
        print("1. git add . && git commit -m 'Add agent validation system'")
        print("2. Run shadow mode: python test_agents.py shadow")  
        print("3. Deploy canary: python test_agents.py canary")
        print("4. Full rollout: python test_agents.py full")

if __name__ == "__main__":
    main()