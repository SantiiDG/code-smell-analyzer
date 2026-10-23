# 🔍 Clean Code Smell Analyzer (CLI)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code Style: Clean Code](https://img.shields.io/badge/Code%20Style-Clean%20Code-brightgreen.svg)](https://clean-code-developer.com/)

Un analizador estático de arquitectura y código limpio en Python (**un único archivo autónomo**) diseñado para auditar proyectos y detectar **code smells** y deuda técnica de forma exhaustiva, directa y accionable.

---

## ✨ Características Principales

- **Arquitectura Zero-Setup:** Implementado en un único archivo autónomo (`smell_analyzer.py`).
- **Análisis de Alta Precisión (AST):** Inspección sintáctica profunda para Python mediante árboles de sintaxis abstracta (`ast`) con filtrado inteligente de falsos positivos.
- **Soporte Polyglot:** Heurísticas y análisis léxico multilingüe para JavaScript, TypeScript, Java, C#, C++, Go, PHP y Ruby.
- **Interfaz Visual Rica:** Tablas coloreadas, paneles y barras visuales mediante [`rich`](https://github.com/Textualize/rich) con degradación elegante a ANSI estándar en entornos CI/CD.
- **Exclusión Inteligente:** Omite automáticamente `.git`, `node_modules`, `venv`, `__pycache__`, minificados (`*.min.js`) y binarios.
- **Auditoría Accionable:** Cada smell incluye ruta exacta, número de línea, severidad, diagnóstico técnico y **sugerencia de refactorización concreta** (Martin Fowler).
- **Exportación a Markdown:** Genera informes ejecutivos (`smells_report.md`) con Health Score, Top 3 de prioridades y tablas detalladas.

---

## 🔎 Code Smells Detectados

| Smell | Severidad | Descripción y Heurística | Sugerencia de Refactorización |
| :--- | :---: | :--- | :--- |
| **Long Method / Function** | `ALTA` / `CRÍTICA` | Métodos con más de $N$ líneas (por defecto: 35). | *Extract Method* / Principio SLAP |
| **God Class / Large File** | `ALTA` / `CRÍTICA` | Clases con > 200 líneas o > 12 métodos; archivos > 300 líneas. | *Single Responsibility Principle (SRP)* / *Facade* |
| **Deep Nesting** | `ALTA` / `CRÍTICA` | Bloques anidados (`if`, `for`, `while`, `try`) con más de 3 niveles. | *Guard Clauses* (retornos tempranos) |
| **Long Parameter List** | `MEDIA` / `ALTA` | Funciones con más de 4-5 parámetros. | *Introduce Parameter Object* / DTO / Dataclass |
| **Magic Numbers** | `MEDIA` | Números literales directos en lógica sin asignar a constantes. | Extraer a constante en `MAYÚSCULAS` o `Enum` |
| **Dead / Commented-out Code** | `MEDIA` / `ALTA` | Bloques de código muerto comentado (>= 3 líneas). | Eliminación de código obsoleto (preservado por Git) |
| **Complex Conditions** | `ALTA` | Expresiones booleanas con $\ge 3$ operadores lógicos encadenados. | *Explaining Variables* / Funciones predicado |

---

## 🚀 Instalación y Requisitos

Requiere **Python 3.10 o superior**.

```bash
# Clonar el repositorio
git clone https://github.com/SantiiDG/code-smell-analyzer.git
cd code-smell-analyzer

# (Opcional, pero recomendado) Instalar Rich para formateo visual avanzado
pip install rich
```

---

## 💻 Guía de Uso

### 1. Escanear el directorio actual
```bash
python smell_analyzer.py
```

### 2. Escanear otro proyecto en cualquier ruta
```bash
python smell_analyzer.py --path "C:\ruta\a\tu\proyecto"
```

### 3. Generar informe en formato Markdown
```bash
python smell_analyzer.py --path . --export smells_report.md
```

### 4. Filtrar por lenguaje específico
```bash
# Solo Python
python smell_analyzer.py --lang py

# Solo JavaScript / TypeScript
python smell_analyzer.py --lang js
```

### 5. Filtrar por nivel de severidad
Muestra únicamente problemas de alta prioridad (`ALTA` y `CRÍTICA`):
```bash
python smell_analyzer.py --severity ALTA
```

### 6. Ajustar umbrales personalizados
Adapta las métricas a las directrices de tu equipo:
```bash
python smell_analyzer.py --max-line-func 25 --max-params 3 --max-nesting 2
```

---

## ⚙️ Parámetros CLI

```text
Opciones:
  -h, --help            Muestra la ayuda y sale.
  --path PATH           Ruta de la carpeta o archivo a analizar (defecto: .).
  --lang LANG           Lenguaje a inspeccionar: py, js, ts, java, c, cs, go o all (defecto: all).
  --max-line-func N     Límite de líneas por función (defecto: 35).
  --max-line-file N     Límite de líneas por archivo (defecto: 300).
  --max-params N        Límite de parámetros por función (defecto: 4).
  --max-nesting N       Profundidad máxima de anidación (defecto: 3).
  --export FILE.md      Exportar auditoría a formato Markdown.
  --severity {MEDIA,ALTA,CRITICA}
                        Filtrar por severidad mínima.
  --no-color            Desactivar colores ANSI (modo texto plano).
```

---

## 📊 Sistema de Puntuación (Health Score)

El analizador evalúa la densidad de penalizaciones por cada 100 líneas de código:
- **`A+` / `A` (90 - 100 pts):** Excelente salud arquitectónica. Deuda técnica insignificante.
- **`B` (80 - 89 pts):** Aceptable. Requiere refactorizaciones preventivas puntuales.
- **`C` (70 - 79 pts):** Regular. Acumulación moderada de acoplamiento y smells.
- **`D` (60 - 69 pts):** Deficiente. Alto riesgo de regresión ante cambios.
- **`F` (< 60 pts):** Crítico. Urgente necesidad de refactorización y rediseño.

---

## 📄 Licencia

Este proyecto se distribuye bajo la licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.
