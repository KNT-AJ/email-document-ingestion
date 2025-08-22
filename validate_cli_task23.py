#!/usr/bin/env python3
"""
CLI Validation Script for Admin Commands (Task 23)

This script validates the implementation of admin CLI commands without
requiring external dependencies. It checks the CLI structure and 
command organization.
"""

import ast
import os
import sys

def validate_cli_structure():
    """Validate the CLI structure by parsing the cli.py file."""
    
    cli_path = "cli.py"
    if not os.path.exists(cli_path):
        print("❌ cli.py file not found")
        return False
    
    try:
        with open(cli_path, 'r') as f:
            content = f.read()
        
        # Parse the AST
        tree = ast.parse(content)
        
        # Check for required imports
        required_imports = ['typer', 'uvicorn', 'subprocess', 'os']
        found_imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                found_imports.append(node.module)
        
        missing_imports = [imp for imp in required_imports if imp not in found_imports]
        if missing_imports:
            print(f"❌ Missing imports: {missing_imports}")
            return False
        else:
            print("✅ All required imports found")
        
        # Check for Typer app creation
        app_created = False
        labels_app_created = False
        watch_app_created = False
        metrics_app_created = False
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id == 'app':
                            app_created = True
                        elif target.id == 'labels_app':
                            labels_app_created = True
                        elif target.id == 'watch_app':
                            watch_app_created = True
                        elif target.id == 'metrics_app':
                            metrics_app_created = True
        
        if app_created:
            print("✅ Main Typer app created")
        else:
            print("❌ Main Typer app not found")
            return False
        
        if labels_app_created and watch_app_created and metrics_app_created:
            print("✅ All sub-applications created")
        else:
            print("❌ Missing sub-applications")
            return False
        
        # Check for command functions
        required_commands = [
            'labels_list', 'labels_ensure', 'labels_assign',
            'watch_start', 'watch_stop', 'watch_status',
            'metrics_dump', 'metrics_summary'
        ]
        
        found_functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                found_functions.append(node.name)
        
        missing_commands = [cmd for cmd in required_commands if cmd not in found_functions]
        if missing_commands:
            print(f"❌ Missing command functions: {missing_commands}")
            return False
        else:
            print("✅ All required command functions found")
        
        # Check for decorators (command decorators)
        decorator_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    # Check for @app.command(), @labels_app.command(), etc.
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            if decorator.func.attr == 'command':
                                decorator_count += 1
                    elif isinstance(decorator, ast.Attribute):
                        if decorator.attr == 'command':
                            decorator_count += 1
        
        # Also check string content for command decorators since AST might miss some patterns
        command_decorator_patterns = [
            '@app.command()',
            '@labels_app.command(',
            '@watch_app.command(',
            '@metrics_app.command('
        ]
        
        string_decorator_count = 0
        for pattern in command_decorator_patterns:
            string_decorator_count += content.count(pattern)
        
        total_decorators = max(decorator_count, string_decorator_count)
        
        if total_decorators >= len(required_commands):
            print(f"✅ Command decorators found ({total_decorators})")
        else:
            print(f"❌ Insufficient command decorators ({total_decorators})")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error parsing cli.py: {e}")
        return False

def validate_command_help_text():
    """Check that commands have proper help text and examples."""
    
    cli_path = "cli.py"
    try:
        with open(cli_path, 'r') as f:
            content = f.read()
        
        # Check for help text patterns
        help_patterns = [
            'This command',
            'Examples:',
            'python cli.py',
            'help='
        ]
        
        found_patterns = []
        for pattern in help_patterns:
            if pattern in content:
                found_patterns.append(pattern)
        
        if len(found_patterns) == len(help_patterns):
            print("✅ Help text patterns found")
            return True
        else:
            missing = [p for p in help_patterns if p not in found_patterns]
            print(f"❌ Missing help text patterns: {missing}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking help text: {e}")
        return False

def validate_error_handling():
    """Check for proper error handling patterns."""
    
    cli_path = "cli.py"
    try:
        with open(cli_path, 'r') as f:
            content = f.read()
        
        # Check for error handling patterns
        error_patterns = [
            'try:',
            'except',
            'typer.Exit(1)',
            'logger.error',
            'typer.secho'
        ]
        
        found_patterns = []
        for pattern in error_patterns:
            if pattern in content:
                found_patterns.append(pattern)
        
        if len(found_patterns) >= 4:  # We expect most patterns
            print("✅ Error handling patterns found")
            return True
        else:
            print(f"❌ Insufficient error handling patterns: {found_patterns}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking error handling: {e}")
        return False

def validate_confirmation_prompts():
    """Check for confirmation prompts on destructive operations."""
    
    cli_path = "cli.py"
    try:
        with open(cli_path, 'r') as f:
            content = f.read()
        
        # Check for confirmation patterns
        confirmation_patterns = [
            'typer.confirm',
            '--dry-run',
            '--confirm'
        ]
        
        found_patterns = []
        for pattern in confirmation_patterns:
            if pattern in content:
                found_patterns.append(pattern)
        
        if len(found_patterns) >= 2:  # We expect confirmation and dry-run
            print("✅ Confirmation prompt patterns found")
            return True
        else:
            print(f"❌ Missing confirmation patterns: {found_patterns}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking confirmation prompts: {e}")
        return False

def main():
    """Run all validation checks."""
    
    print("🔍 Validating Admin CLI Commands Implementation (Task 23)")
    print("=" * 60)
    
    all_passed = True
    
    print("\n📋 Checking CLI Structure...")
    if not validate_cli_structure():
        all_passed = False
    
    print("\n📝 Checking Help Text...")
    if not validate_command_help_text():
        all_passed = False
    
    print("\n🛡️ Checking Error Handling...")
    if not validate_error_handling():
        all_passed = False
    
    print("\n⚠️ Checking Confirmation Prompts...")
    if not validate_confirmation_prompts():
        all_passed = False
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("🎉 All validation checks passed!")
        print("\n✅ Task 23 Implementation Summary:")
        print("   • Gmail label management commands (list, ensure, assign)")
        print("   • Gmail watch commands (start, stop, status)")
        print("   • Metrics commands (dump, summary)")
        print("   • Proper CLI organization with sub-commands")
        print("   • Comprehensive help text and examples")
        print("   • Error handling and validation")
        print("   • Confirmation prompts for destructive operations")
        print("\n🚀 Ready for testing with actual Gmail and Pub/Sub services!")
        return 0
    else:
        print("❌ Some validation checks failed!")
        print("   Please review the implementation and fix any issues.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
