# 🎨 Vanna Grok - Beautiful Output Examples

> **Enhanced Vanna AI with Colombian number formatting and AI-powered insights**

---

## ✨ New Features

### 1. **Beautiful Number Formatting** 💰
- **Colombian Pesos**: `$123.456.789` (period as thousands separator)
- **Percentages**: `45,6%` (comma as decimal separator)
- **Quantities**: `1.234` units (period as thousands separator)
- **Auto-detection**: Based on column names (Revenue, Ganancia, Margen, etc.)

### 2. **AI-Generated Insights** 🤖
- **Executive Summary**: Quick overview of what the data shows
- **Key Insights**: 2-3 important findings
- **Action Recommendations**: Concrete business actions to take
- **Spanish**: Optimized for Colombian hardware store context

### 3. **Enhanced Presentation** 📊
- Clean, formatted output
- Emoji indicators
- Professional layout
- Spanish business terminology

---

## 📝 Example Outputs

### Example 1: Top Selling Products

**Question (Spanish):**
```
Top 10 productos más vendidos este año
```

**Output:**
```
======================================================================
📊 RESULTADOS (con formato colombiano)
======================================================================

📝 SQL Ejecutado:
SELECT TOP 10
    ArticulosNombre AS Producto,
    SUM(Cantidad) AS Unidades_Vendidas,
    SUM(TotalMasIva) AS Revenue
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
  AND YEAR(Fecha) = YEAR(GETDATE())
GROUP BY ArticulosNombre
ORDER BY Revenue DESC

✅ 10 filas encontradas

Producto                                    Unidades_Vendidas  Revenue
------------------------------------------  -----------------  ----------------
CEMENTO GRIS ARGOS x 50KG                   2.456              $45.678.900
VARILLA CORRUGADA 3/8" x 6M                 1.892              $38.234.567
ARENA LAVADA m³                             845                $29.456.789
TUBO PVC 4" PRESIÓN x 6M                    1.234              $24.567.890
LADRILLO TOLETE COMÚN                       15.678             $19.345.678
CABLE THHN #12 AWG x METRO                  5.432              $18.234.567
PINTURA VINILO BLANCO GALON                 876                $15.678.900
CEMENTO BLANCO ARGOS x 1KG                  3.456              $12.345.678
PEGANTE BALDOSA x 25KG                      567                $9.876.543
TORNILLO DRYWALL 6x1" CAJA x100             2.345              $8.765.432

======================================================================
🤖 ANÁLISIS INTELIGENTE (Powered by Grok)
======================================================================

📊 **Resumen Ejecutivo**
Los datos muestran que los materiales de construcción básicos dominan las ventas,
con cemento gris liderando con $45.6M en ingresos y 2.456 unidades vendidas.

💡 **Insights Clave**
• El cemento y la varilla representan el 43% del revenue total del top 10
• Alta rotación en productos de volumen (ladrillo: 15.678 unidades)
• Los productos de acabados (pintura, tornillos) tienen ticket promedio más alto

🎯 **Recomendaciones**
1. **Inventario**: Asegurar stock permanente de cemento y varilla (productos estrella)
2. **Promoción**: Crear combos con cemento + varilla + arena para proyectos
3. **Cross-selling**: Cuando vendan ladrillos, sugerir pegante y cemento blanco
4. **Pricing**: Revisar márgenes en cable THHN (#6 en ventas) - puede tener oportunidad
5. **Logística**: Optimizar almacenaje de productos de volumen (arena, ladrillo)

======================================================================
```

---

### Example 2: Profit Margins by Category

**Question (Spanish):**
```
Margen de ganancia promedio por categoría
```

**Output:**
```
======================================================================
📊 RESULTADOS (con formato colombiano)
======================================================================

📝 SQL Ejecutado:
SELECT
    categoria,
    COUNT(*) AS Transacciones,
    SUM(TotalSinIva) AS Revenue_Neto,
    SUM(TotalSinIva - ValorCosto) AS Ganancia,
    AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0)) AS Margen_Promedio_Pct
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS') AND TotalSinIva > 0
GROUP BY categoria
ORDER BY Margen_Promedio_Pct DESC

✅ 15 filas encontradas

categoria                          Transacciones  Revenue_Neto     Ganancia         Margen_Promedio_Pct
---------------------------------  -------------  ---------------  ---------------  --------------------
HERRAMIENTAS ELECTRICAS            1.234          $89.456.789      $35.678.901      39,9%
FERRETERIA Y CERRAJERIA            2.567          $145.234.678     $52.345.678      36,0%
PINTURA Y ACABADOS                 876            $67.890.123      $23.456.789      34,5%
PLOMERIA Y ACCESORIOS              1.987          $98.765.432      $32.109.876      32,5%
ELECTRICIDAD                       1.456          $76.543.210      $23.456.789      30,7%
MATERIALES DE CONSTRUCCION         5.432          $234.567.890     $65.432.109      27,9%
PEGANTES Y SELLADORES              678            $34.567.890      $9.345.678       27,0%
MADERA Y DERIVADOS                 892            $56.789.012      $14.567.890      25,6%
PISOS Y ENCHAPES                   567            $123.456.789     $29.876.543      24,2%
ACERO Y METALES                    2.345          $187.654.321     $42.345.678      22,6%
CEMENTO Y AGLOMERANTES             3.456          $298.765.432     $62.345.678      20,9%
ARENA Y AGREGADOS                  1.234          $89.456.789      $15.678.901      17,5%
LADRILLOS Y BLOQUES                4.567          $198.765.432     $31.234.567      15,7%

======================================================================
🤖 ANÁLISIS INTELIGENTE (Powered by Grok)
======================================================================

📊 **Resumen Ejecutivo**
Las herramientas eléctricas lideran en márgenes (39,9%), mientras que productos
de volumen como cemento (20,9%) y ladrillos (15,7%) tienen márgenes más bajos
pero generan alto revenue.

💡 **Insights Clave**
• **Alta rentabilidad**: Herramientas, ferretería y pintura (>34% margen)
• **Alto volumen, bajo margen**: Cemento ($298M revenue, 20,9% margen)
• **Oportunidad**: Arena y ladrillos tienen márgenes muy bajos (<18%)
• **Balance perfecto**: Plomería combina buen margen (32,5%) con volumen alto

🎯 **Recomendaciones**
1. **Push de margen alto**: Capacitar vendedores para promover herramientas eléctricas
   y ferretería (mejor comisión en productos 35%+ margen)

2. **Revisión de precios**:
   - Arena (17,5%): Revisar costos de proveedor o ajustar precio de venta
   - Ladrillos (15,7%): Analizar si hay subsidio cruzado con otros productos

3. **Mix de productos**: En ventas grandes de construcción (cemento, ladrillo),
   agregar productos de mayor margen (pegantes, herramientas)

4. **Focus estratégico**:
   - Volumen: Cemento, acero, materiales construcción (tracción de clientes)
   - Margen: Herramientas, ferretería, pintura (rentabilidad)

5. **Promociones inteligentes**: Descuentos en cemento/ladrillos SOLO si compran
   también productos de margen alto (ferretería, pintura)

======================================================================
```

---

### Example 3: Top Customers

**Question (Spanish):**
```
Top 10 clientes por facturación total
```

**Output:**
```
======================================================================
📊 RESULTADOS (con formato colombiano)
======================================================================

📝 SQL Ejecutado:
SELECT TOP 10
    TercerosNombres AS Cliente,
    COUNT(*) AS Ordenes,
    SUM(TotalMasIva) AS Facturacion_Total,
    AVG(TotalMasIva) AS Ticket_Promedio
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
GROUP BY TercerosNombres
ORDER BY Facturacion_Total DESC

✅ 10 filas encontradas

Cliente                              Ordenes  Facturacion_Total  Ticket_Promedio
----------------------------------  --------  -----------------  ----------------
CONSTRUCTORA EDIFICAR S.A.S.         234       $127.456.789       $544.700
OBRAS Y PROYECTOS LTDA               189       $98.765.432        $522.567
FERRETERIA EL CONSTRUCTOR            456       $89.234.567        $195.690
INVERSIONES INMOBILIARIAS XYZ        98        $76.543.210        $781.053
CONSTRUCCIONES RODRIGUEZ             167       $65.432.109        $391.809
ALMACEN DE MATERIALES LA 80          389       $58.765.432        $151.069
JUAN CARLOS MARTINEZ GOMEZ           523       $45.678.901        $87.349
PROYECTOS URBANOS CIA                67        $42.345.678        $631.935
MARIA FERNANDA LOPEZ TORRES          298       $38.234.567        $128.305
DISTRIBUIDORA ANDINA S.A.            145       $34.567.890        $238.399

======================================================================
🤖 ANÁLISIS INTELIGENTE (Powered by Grok)
======================================================================

📊 **Resumen Ejecutivo**
El top 10 de clientes genera $677M (15% del revenue total estimado), con un
mix entre constructoras B2B (tickets altos) y ferreterías retail (volumen alto).

💡 **Insights Clave**
• **Segmentación clara**:
  - B2B Constructoras: Tickets >$500K (Edificar, Obras y Proyectos, Inversiones)
  - Retail/Ferreterías: Volumen alto, tickets medios (El Constructor, La 80)
  - Particulares: Frecuencia alta, tickets bajos (Juan Carlos Martínez: 523 órdenes)

• **Concentración de riesgo**: El top 3 representa 48% del revenue del top 10

• **Loyalty**: Juan Carlos Martínez (523 órdenes) es cliente fidelizado a pesar
  de ticket bajo - alto valor de por vida (LTV)

🎯 **Recomendaciones**
1. **Account Management B2B**:
   - Asignar ejecutivo dedicado para Edificar, Obras y Proyectos (clientes >$90M)
   - Oferta personalizada: descuentos por volumen, crédito extendido 60 días
   - Visitas trimestrales para proyectos futuros

2. **Programa VIP Retail**:
   - Ferretería El Constructor (456 órdenes): Descuento especial 5% adicional
   - Almacén La 80 (389 órdenes): Entrega prioritaria, stock reservado

3. **Fidelización Particulares**:
   - Juan Carlos Martínez (523 órdenes, $45M): Cliente oro
   - Crear programa de puntos: 1 punto por cada $10.000, canjeable por descuentos
   - Reconocimiento: Invitación eventos, acceso preventa ofertas

4. **Diversificación de riesgo**:
   - Reducir dependencia del top 3 (48% concentración)
   - Meta: Captar 5 nuevos clientes B2B medios (facturación $30-50M/año)

5. **Cross-selling constructoras**:
   - Inversiones XYZ (98 órdenes, ticket $781K): Bajo volumen, alta calidad
   - Ofrecer servicios adicionales: asesoría técnica, logística especializada

======================================================================
```

---

## 🎨 Formatting Rules

### Currency Detection (Colombian Pesos)
Columns containing these keywords get `$XXX.XXX.XXX` format:
- `revenue`, `ganancia`, `facturacion`, `total`
- `costo`, `precio`, `valor`, `ingreso`
- `profit`, `cost`, `iva`

### Percentage Detection
Columns containing these keywords get `XX,X%` format:
- `margen`, `margin`, `pct`, `porcentaje`, `percentage`, `%`

### Quantity Detection
Other numeric columns get `X.XXX` format (thousands separator)

---

## 🤖 AI Insights Components

Each query result includes:

1. **📊 Resumen Ejecutivo**
   - 1-2 sentences summarizing the data
   - High-level takeaway

2. **💡 Insights Clave**
   - 2-3 important findings from the data
   - Patterns, anomalies, opportunities
   - Data-driven observations

3. **🎯 Recomendaciones**
   - 3-5 concrete, actionable recommendations
   - Specific to Colombian hardware store context
   - Business-focused (not just data analysis)

---

## 🚀 Usage

### Ask in Spanish (Optimized)
```python
# In Vanna web UI:
"Top productos rentables este mes"
"Clientes que no han comprado en 90 días"
"Categorías con margen menor al 20%"
"Comparar ventas diciembre vs noviembre"
```

### Ask in English (Works too)
```python
"What are my most profitable products?"
"Show customers by lifetime value"
"Which categories have low margins?"
```

---

## ⚙️ Configuration

Enable/disable features in `.env`:

```bash
# Enable AI insights (default: true)
ENABLE_AI_INSIGHTS=true

# Number formatting locale (default: es_CO)
NUMBER_LOCALE=es_CO

# Max insights tokens (default: 500)
MAX_INSIGHTS_TOKENS=500
```

---

## 📊 Performance

- **Number formatting**: <10ms per query
- **AI insights**: 2-5 seconds (Grok API call)
- **Total overhead**: ~3-5 seconds per query

**Note**: Insights are generated AFTER displaying results, so you see data immediately.

---

## 💡 Tips

1. **Specific questions** = Better insights
   - ❌ "Ventas" (too generic)
   - ✅ "Top 10 productos por margen de ganancia" (specific)

2. **Include time ranges** for trends
   - "Ventas este mes vs mes pasado"
   - "Productos más vendidos este trimestre"

3. **Ask for comparisons** to get actionable insights
   - "Categorías más y menos rentables"
   - "Clientes nuevos vs recurrentes"

---

## 🎉 Benefits

### For Business Users
- ✅ **Understand data** without SQL knowledge
- ✅ **Formatted numbers** in familiar Colombian format
- ✅ **Action recommendations** from AI
- ✅ **Spanish optimized** for local context

### For Analysts
- ✅ **Faster insights** (AI does initial analysis)
- ✅ **Better presentations** (formatted output)
- ✅ **Reproducible** (SQL included in output)
- ✅ **Learning tool** (see how AI interprets data)

---

**Ready to try?** Run `python src/vanna_grok.py` and ask your first question! 🚀
