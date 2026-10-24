# Clean Code Smell Analyzer (CLI)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Health Score: A+](https://img.shields.io/badge/Self--Audit%20Score-A%2B%20(100%2F100)-brightgreen.svg)](https://github.com/SantiiDG/code-smell-analyzer)
[![Code Style: Clean Code](https://img.shields.io/badge/Architecture-Clean%20Code-purple.svg)](https://clean-code-developer.com/)

Un analizador estático de arquitectura y código limpio en Python diseñado para auditar proyectos de software y detectar **code smells**, complejidad ciclomática y deuda técnica de forma exhaustiva, directa y accionable.

> **Dogfooding verificado:** Este propio repositorio pasa su auto-auditoría con **0 Code Smells** y un **Health Score de `A+ (100.0/100)`**.

---

## ✨ Características Principales

- **Análisis Estático AST de Alta Precisión (Python):** Inspección sintáctica mediante árboles de sintaxis abstracta (`ast`). Descuenta automáticamente docstrings al medir longitud de funciones, reconoce escaleras `elif` planas y evita falsos positivos en constantes, Enums y atributos de clase.
- **Motor Heurístico Polyglot Saneado:** Soporte léxico multilingüe para **JavaScript, TypeScript, Java, C#, C++, Go, PHP y Ruby** con limpieza previa de literales de texto y comentarios en línea para un balanceo exacto de llaves `{}`.
- **10 Detectores de Deuda Técnica:** Incluye complejidad ciclomática de McCabe, argumentos mutables por defecto, listas largas de parámetros, anidación profunda, God Classes, condiciones booleanas complejas, números mágicos y código muerto comentado.
- **Interfaz Visual Enriquecida:** Tablas coloreadas, paneles y resúmenes ejecutivos con [`rich`](https://github.com/Textualize/rich) y degradación automática a salida ANSI estándar en entornos sin dependencias o CI/CD.
- **Exportación Dual (Markdown y JSON):** Genera reportes ejecutivos en Markdown (`.md`) para documentación o en JSON estructurado (`.json`) para pipelines de integración continua.

---

## 🏗️ Estructura del Proyecto

El proyecto aplica **Clean Architecture** y el **Principio de Responsabilidad Única (SRP)**:

```text
code-smell-analyzer/
├── smell_analyzer.py             # Punto de entrada CLI principal
├── analyzer/                     # Paquete modular de análisis estático
│   ├── __init__.py
│   ├── constants.py              # Constantes, umbrales y pesos centralizados (0 Magic Numbers)
│   ├── models.py                 # Entidades de dominio, Enums y cálculo de Health Score
│   ├── discovery.py              # Explorador recursivo y filtro de archivos ignorados
│   ├── comment_detector.py       # Heurística poliglota de detección de código comentado
│   ├── python_analyzer.py        # Analizador AST para Python (McCabe, Nesting, SRP, SLAP)
│   ├── polyglot_analyzer.py      # Analizador léxico para JS, TS, Java, C#, C++, Go, PHP
│   ├── engine.py                 # Orquestador central de análisis
│   ├── renderers.py              # Renderizador visual en terminal (Rich UI + Fallback ANSI)
│   ├── exporters.py              # Exportadores a Markdown (.md) y JSON (.json)
│   └── cli.py                    # Configuración de argumentos CLI y flujo de ejecución
├── tests/                        # Suite de pruebas unitarias y test de auto-auditoría
│   └── test_analyzer.py
├── requirements.txt              # Dependencia visual opcional (rich)
├── LICENSE                       # Licencia MIT
└── README.md                     # Documentación técnica
```

---

## 🔎 Catálogo de Code Smells Detectados

| Code Smell | Severidad | Heurística / Regla Estática | Refactorización Recomendada |
| :--- | :---: | :--- | :--- |
| **Long Method / Function** | `ALTA` / `CRÍTICA` | Funciones con más de $N$ líneas efectivas (defecto: 35, excluyendo docstring). | *Extract Method* / Principio SLAP |
| **God Class** | `ALTA` / `CRÍTICA` | Clases con > 200 líneas o > 12 métodos. | *Single Responsibility Principle (SRP)* / *Extract Class* |
| **Large File** | `MEDIA` / `CRÍTICA` | Archivos que superan el umbral de líneas (defecto: 300). | Modularización en submódulos cohesivos |
| **Deep Nesting** | `ALTA` / `CRÍTICA` | Bloques de control (`if`, `for`, `while`, `try`) con profundidad > 3. | *Guard Clauses* (retornos tempranos) |
| **High Cyclomatic Complexity** | `ALTA` / `CRÍTICA` | Complejidad ciclomática de McCabe > 10 puntos de decisión. | Polimorfismo, tablas de despacho o extracción |
| **Long Parameter List** | `MEDIA` / `ALTA` | Funciones o métodos con más de 4 parámetros (excluye `self`/`cls`). | *Introduce Parameter Object* / Dataclass / DTO |
| **Complex Condition** | `ALTA` | Expresiones booleanas con $\ge 3$ operadores lógicos encadenados. | *Explaining Variables* o funciones predicado |
| **Mutable Default Argument** | `ALTA` | Uso de `[]`, `{}` o `set()` como valor por defecto en firmas Python. | Usar `None` e inicializar dentro de la función |
| **Dead / Commented-out Code** | `MEDIA` / `ALTA` | Bloques de $\ge 3$ líneas consecutivas de código comentado. | Eliminar código obsoleto (resguardado por Git) |
| **Magic Number** | `MEDIA` | Números literales en lógica sin asignar a constantes descriptivas. | Extraer a constante en `MAYÚSCULAS` o `Enum` |

---

## 🚀 Instalación

Requiere **Python 3.10 o superior**.

```bash
git clone https://github.com/SantiiDG/code-smell-analyzer.git
cd code-smell-analyzer
pip install -r requirements.txt
```

---

## 💻 Guía de Uso

### 1. Analizar el directorio actual
```bash
python smell_analyzer.py
```

### 2. Analizar otro proyecto externo en cualquier carpeta
```bash
python smell_analyzer.py --path "C:\ruta\a\tu\proyecto"
```

### 3. Exportar auditoría a Markdown o JSON
```bash
# Exportar informe visual en Markdown
python smell_analyzer.py --path . --export smells_report.md

# Exportar datos estructurados en JSON (ideal para CI/CD)
python smell_analyzer.py --path . --export smells_report.json
```

### 4. Filtrar por lenguaje, severidad o exclusiones
```bash
# Analizar únicamente Python y mostrar solo severidad ALTA y CRÍTICA
python smell_analyzer.py --lang py --severity ALTA

# Excluir carpetas o archivos específicos adicionales
python smell_analyzer.py --exclude migrations legacy_scripts
```

### 5. Personalizar umbrales de arquitectura
```bash
python smell_analyzer.py --max-line-func 25 --max-params 3 --max-nesting 2 --max-complexity 8
```

---

## 🧪 Ejecutar Pruebas Unitarias

El proyecto incluye una suite de tests automatizados con `unittest` (incluyendo un test de auto-auditoría que garantiza `0 smells` en el propio repositorio):

```bash
python -m unittest discover -s tests -v
```

---

## 📄 Licencia

Distribuido bajo la licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más información.
