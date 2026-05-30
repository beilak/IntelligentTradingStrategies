#!/bin/bash

echo "Анализ репозитория..."
echo ""

# 1. Размер репозитория без .git, .env, .venv, кэшей и тестовых данных
echo "1. Размер репозитория (без .git, .env, .venv, кэшей и тестовых данных):"

# Находим все файлы, исключая ненужные пути, и суммируем их размер
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    total_size=$(find . -type f \
        -not -path "./.git/*" \
        -not -path "./.env/*" \
        -not -path "./.venv/*" \
        -not -path "*/venv/*" \
        -not -path "./node_modules/*" \
        -not -path "*/__pycache__/*" \
        -not -path "*/.pytest_cache/*" \
        -not -path "*/test_data/*" \
        -not -path "*/tests/data/*" \
        2>/dev/null -exec stat -f%z {} + | awk '{s+=$1} END {print s}')
else
    # Linux
    total_size=$(find . -type f \
        -not -path "./.git/*" \
        -not -path "./.env/*" \
        -not -path "./.venv/*" \
        -not -path "*/venv/*" \
        -not -path "./node_modules/*" \
        -not -path "*/__pycache__/*" \
        -not -path "*/.pytest_cache/*" \
        -not -path "*/test_data/*" \
        -not -path "*/tests/data/*" \
        2>/dev/null -exec stat -c%s {} + | awk '{s+=$1} END {print s}')
fi

if [ -z "$total_size" ]; then
    total_size=0
fi

# Конвертируем в читаемый формат
if [ $total_size -ge 1073741824 ]; then
    size_gb=$(echo "scale=2; $total_size / 1073741824" | bc)
    echo "   $size_gb GB ($total_size bytes)"
elif [ $total_size -ge 1048576 ]; then
    size_mb=$(echo "scale=2; $total_size / 1048576" | bc)
    echo "   $size_mb MB ($total_size bytes)"
elif [ $total_size -ge 1024 ]; then
    size_kb=$(echo "scale=2; $total_size / 1024" | bc)
    echo "   $size_kb KB ($total_size bytes)"
else
    echo "   $total_size bytes"
fi
echo ""

# 2. Строки кода в .py файлах
echo "2. Количество строк кода в Python файлах (.py, без venv и .git):"
py_files=$(find . -name "*.py" \
    -not -path "./.git/*" \
    -not -path "./.venv/*" \
    -not -path "*/venv/*" \
    -not -path "*/node_modules/*" \
    2>/dev/null)

if [ -n "$py_files" ]; then
    py_lines=$(echo "$py_files" | xargs wc -l 2>/dev/null | tail -1)
    echo "   $py_lines"
else
    echo "   Нет Python файлов"
fi
echo ""

# 3. Строки кода в UI файлах
echo "3. Количество строк кода в UI файлах (JS/Vue/TypeScript):"
ui_files=$(find . \( -name "*.js" -o -name "*.vue" -o -name "*.ts" -o -name "*.tsx" -o -name "*.jsx" \) \
    -not -path "./.git/*" \
    -not -path "./.venv/*" \
    -not -path "*/venv/*" \
    -not -path "*/node_modules/*" \
    2>/dev/null)

if [ -n "$ui_files" ]; then
    ui_lines=$(echo "$ui_files" | xargs wc -l 2>/dev/null | tail -1)
    echo "   $ui_lines"
else
    echo "   Нет UI файлов"
fi
echo ""

echo "Готово!"
