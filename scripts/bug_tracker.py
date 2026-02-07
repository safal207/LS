#!/usr/bin/env python3
"""
Bug Tracker Script
Автоматический анализатор кода на потенциальные баги
"""

import ast
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple


class BugPattern:
    """Bug detection patterns"""
    
    PATTERNS = {
        'bare_except': {
            'pattern': r'except\s*:\s*$|except\s+Exception\s*:',
            'severity': 'MEDIUM',
            'message': 'Bare except catches KeyboardInterrupt and SystemExit',
            'fix': 'Use specific exceptions (except ValueError:)'
        },
        'sys_exit': {
            'pattern': r'sys\.exit\([^)]*\)',
            'severity': 'HIGH',
            'message': 'sys.exit() outside __main__ breaks imports',
            'fix': 'Check if __name__ == "__main__":'
        },
        'index_access': {
            'pattern': r'\[0\]',
            'severity': 'MEDIUM',
            'message': 'Potential IndexError if list is empty',
            'fix': 'Check if len(list) > 0 before accessing'
        },
        'division': {
            'pattern': r'/\s*\w+|/\s*\d+',
            'severity': 'MEDIUM',
            'message': 'Potential division by zero',
            'fix': 'Check denominator before division'
        },
        'hardcoded_path': {
            'pattern': r'["\']/[\w/]+["\']|["\']\\[\w\\]+["\']',
            'severity': 'LOW',
            'message': 'Hardcoded path',
            'fix': 'Use pathlib.Path or os.path'
        },
        'print_debug': {
            'pattern': r'print\s*\(',
            'severity': 'LOW',
            'message': 'Using print instead of logging',
            'fix': 'Replace with logger.info/debug/error'
        },
        'todo_fixme': {
            'pattern': r'#\s*(TODO|FIXME|XXX|HACK)',
            'severity': 'LOW',
            'message': 'Unfinished task',
            'fix': 'Create issue or complete the task'
        }
    }


def analyze_file(filepath: Path) -> List[Dict]:
    """Анализирует файл на наличие багов"""
    bugs = []
    content = filepath.read_text(encoding='utf-8', errors='ignore')
    lines = content.split('\n')
    
    for bug_type, info in BugPattern.PATTERNS.items():
        for i, line in enumerate(lines, 1):
            if re.search(info['pattern'], line):
                # Проверяем, что это не комментарий
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                
                bugs.append({
                    'file': str(filepath),
                    'line': i,
                    'type': bug_type,
                    'severity': info['severity'],
                    'message': info['message'],
                    'fix': info['fix'],
                    'code': line.strip()[:80]
                })
    
    return bugs


def analyze_ast(filepath: Path) -> List[Dict]:
    """AST анализ для сложных паттернов"""
    bugs = []
    content = filepath.read_text(encoding='utf-8', errors='ignore')
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return [{'file': str(filepath), 'line': 0, 'type': 'syntax_error', 
                 'severity': 'CRITICAL', 'message': 'Syntax Error', 
                 'fix': 'Исправьте синтаксис Python', 'code': ''}]
    
    for node in ast.walk(tree):
        # Проверка на неправильный порядок полей в dataclass
        if isinstance(node, ast.ClassDef):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name) and decorator.id == 'dataclass':
                    # Проверяем поля
                    has_default = False
                    for item in node.body:
                        if isinstance(item, ast.AnnAssign) and item.target:
                            has_field_default = False
                            if item.value and isinstance(item.value, ast.Call):
                                if isinstance(item.value.func, ast.Name) and item.value.func.id == 'field':
                                    has_field_default = True
                            
                            if has_default and not has_field_default and item.value:
                                bugs.append({
                                    'file': str(filepath),
                                    'line': item.lineno,
                                    'type': 'dataclass_field_order',
                                    'severity': 'CRITICAL',
                                    'message': 'Non-default field after default field in dataclass',
                                    'fix': 'Reorder fields - non-default first, then with defaults',
                                    'code': f'{item.target.id}: ... = {ast.dump(item.value)[:40]}'
                                })
                            
                            if item.value:
                                has_default = True
        
        # Проверка на unreachable code
        if isinstance(node, ast.FunctionDef):
            found_return = False
            for stmt in node.body:
                if found_return and not isinstance(stmt, (ast.Expr, ast.Pass)):
                    bugs.append({
                        'file': str(filepath),
                        'line': stmt.lineno,
                        'type': 'unreachable_code',
                        'severity': 'HIGH',
                        'message': 'Unreachable code after return statement',
                        'fix': 'Remove unreachable code or move before return',
                        'code': ast.dump(stmt)[:60]
                    })
                if isinstance(stmt, ast.Return):
                    found_return = True
    
    return bugs


def scan_directory(directory: Path, exclude_dirs: List[str] = None) -> List[Dict]:
    """Scan directory for bugs"""
    if exclude_dirs is None:
        exclude_dirs = ['__pycache__', '.git', 'venv', '.venv', 'node_modules']
    
    all_bugs = []
    
    for root, dirs, files in os.walk(directory):
        # Exclude unnecessary directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith('.py'):
                filepath = Path(root) / file
                bugs = analyze_file(filepath)
                bugs.extend(analyze_ast(filepath))
                all_bugs.extend(bugs)
    
    return all_bugs


def print_report(bugs: List[Dict]):
    """Выводит отчет о багах"""
    if not bugs:
        print("✅ Багов не найдено!")
        return
    
    # Сортируем по severity
    severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    bugs.sort(key=lambda x: severity_order.get(x['severity'], 99))
    
    print(f"\n{'='*80}")
    print(f"BUGS FOUND: {len(bugs)}")
    print(f"{'='*80}\n")
    
    current_severity = None
    for bug in bugs:
        if bug['severity'] != current_severity:
            current_severity = bug['severity']
            marker = {'CRITICAL': '[!!!]', 'HIGH': '[!!]', 'MEDIUM': '[!]', 'LOW': '[i]'}.get(current_severity, '[?]')
            print(f"\n{marker} {current_severity} SEVERITY\n")
        
        print(f"FILE: {bug['file']}:{bug['line']}")
        print(f"   Type: {bug['type']}")
        print(f"   Issue: {bug['message']}")
        print(f"   Code: {bug['code']}")
        print(f"   Fix: {bug['fix']}")
        print()


def main():
    """Главная функция"""
    directories = ['codex', 'python']
    
    all_bugs = []
    for directory in directories:
        if os.path.exists(directory):
            bugs = scan_directory(Path(directory))
            all_bugs.extend(bugs)
    
    print_report(all_bugs)
    
    # Выход с кодом ошибки если есть критичные баги
    critical_count = sum(1 for bug in all_bugs if bug['severity'] == 'CRITICAL')
    if critical_count > 0:
        print(f"\n⚠️  Найдено {critical_count} критичных багов!")
        sys.exit(1)


if __name__ == '__main__':
    main()
