"""
Streamlit Interactive Dashboard
===============================
Modern web-based dashboard that replaces static PNG reports.

Run with: streamlit run streamlit_dashboard.py

Benefits over current approach:
- Interactive charts (zoom, pan, filter)
- Web-based (no installation for users)
- Auto-refresh capability
- Multiple export formats
- Real-time data updates
- User-friendly filters
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sqlalchemy import create_engine

# Page configuration
st.set_page_config(
    page_title="Business Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2E86AB;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #2E86AB;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Data Loading Functions
# ============================================================================

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data(connection_string: str, start_date: str, end_date: str, limit: int = 50000):
    """Load data from database with caching"""
    engine = create_engine(connection_string)

    query = f"""
    SELECT TOP {limit}
        Fecha,
        TotalMasIva,
        TotalSinIva,
        ValorCosto,
        Cantidad,
        TercerosNombres as customer_name,
        ArticulosNombre as product_name,
        ArticulosCodigo as product_code,
        categoria as category,
        subcategoria as subcategory
    FROM banco_datos
    WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        AND Fecha BETWEEN :start_date AND :end_date
    """

    df = pd.read_sql(
        query,
        engine,
        params={"start_date": start_date, "end_date": end_date}
    )

    # Data type conversions
    df['Fecha'] = pd.to_datetime(df['Fecha'])
    df['TotalMasIva'] = pd.to_numeric(df['TotalMasIva'], errors='coerce')
    df['TotalSinIva'] = pd.to_numeric(df['TotalSinIva'], errors='coerce')
    df['ValorCosto'] = pd.to_numeric(df['ValorCosto'], errors='coerce')

    return df


def calculate_metrics(df: pd.DataFrame) -> dict:
    """Calculate all business metrics"""
    return {
        "total_revenue": df['TotalMasIva'].sum(),
        "total_orders": len(df),
        "avg_order_value": df['TotalMasIva'].mean(),
        "total_cost": df['ValorCosto'].sum(),
        "gross_profit": (df['TotalSinIva'] - df['ValorCosto']).sum(),
        "profit_margin": (
            ((df['TotalSinIva'] - df['ValorCosto']).sum() / df['TotalSinIva'].sum() * 100)
            if df['TotalSinIva'].sum() > 0 else 0
        )
    }


# ============================================================================
# Sidebar Configuration
# ============================================================================

with st.sidebar:
    st.image("https://via.placeholder.com/150x50/2E86AB/FFFFFF?text=Logo", width=150)
    st.title("⚙️ Configuration")

    # Date range selector
    st.subheader("📅 Date Range")
    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now() - timedelta(days=30),
            max_value=datetime.now()
        )

    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now(),
            max_value=datetime.now()
        )

    # Data limit
    limit = st.slider(
        "Max Records",
        min_value=1000,
        max_value=100000,
        value=50000,
        step=1000,
        help="Limit number of records to prevent performance issues"
    )

    # Filters
    st.subheader("🔍 Filters")
    show_negative_margins = st.checkbox("Show negative margins only", False)
    min_revenue = st.number_input("Min Revenue ($)", min_value=0, value=0)

    # Refresh button
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # Export options
    st.subheader("📥 Export")
    export_format = st.selectbox("Format", ["Excel", "CSV", "PDF"])

    # Database connection (in real app, use st.secrets)
    st.subheader("🔐 Connection")
    with st.expander("Database Settings"):
        st.info("Using credentials from .env file")


# ============================================================================
# Main Dashboard
# ============================================================================

# Header
st.markdown('<p class="main-header">📊 Business Analytics Dashboard</p>',
            unsafe_allow_html=True)
st.caption(f"Data from {start_date} to {end_date}")

# Load data
try:
    with st.spinner("Loading data..."):
        # In real app, get connection string from st.secrets
        connection_string = st.secrets.get(
            "db_connection",
            "mssql+pymssql://user:pass@localhost:1433/SmartBusiness"
        )

        df = load_data(
            connection_string,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            limit
        )

        if len(df) == 0:
            st.warning("⚠️ No data found for selected date range")
            st.stop()

        # Calculate metrics
        metrics = calculate_metrics(df)

except Exception as e:
    st.error(f"❌ Error loading data: {str(e)}")
    st.info("💡 Make sure database connection is configured in .streamlit/secrets.toml")
    st.stop()

# ============================================================================
# KPI Cards
# ============================================================================

st.subheader("📈 Key Performance Indicators")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Revenue",
        f"${metrics['total_revenue']:,.2f}",
        help="Total revenue with IVA"
    )

with col2:
    st.metric(
        "Total Orders",
        f"{metrics['total_orders']:,}",
        help="Number of transactions"
    )

with col3:
    st.metric(
        "Avg Order Value",
        f"${metrics['avg_order_value']:,.2f}",
        help="Average revenue per order"
    )

with col4:
    profit_color = "normal" if metrics['profit_margin'] > 0 else "inverse"
    st.metric(
        "Profit Margin",
        f"{metrics['profit_margin']:.1f}%",
        delta=f"${metrics['gross_profit']:,.2f}",
        delta_color=profit_color,
        help="Gross profit margin"
    )

st.divider()

# ============================================================================
# Tabs for Different Views
# ============================================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Overview",
    "👥 Customers",
    "📦 Products",
    "🏭 Categories",
    "📈 Trends"
])

# --------------------
# Tab 1: Overview
# --------------------
with tab1:
    st.header("Business Overview")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Revenue vs Cost")

        # Revenue breakdown
        revenue_breakdown = pd.DataFrame({
            'Metric': ['Revenue (excl. IVA)', 'Cost', 'Profit'],
            'Amount': [
                df['TotalSinIva'].sum(),
                df['ValorCosto'].sum(),
                metrics['gross_profit']
            ]
        })

        fig = px.bar(
            revenue_breakdown,
            x='Metric',
            y='Amount',
            color='Metric',
            color_discrete_sequence=['#2E86AB', '#C73E1D', '#6A994E']
        )
        fig.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Monthly Trend")

        # Monthly aggregation
        df['Month'] = df['Fecha'].dt.to_period('M').astype(str)
        monthly = df.groupby('Month').agg({
            'TotalMasIva': 'sum',
            'ValorCosto': 'sum'
        }).reset_index()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=monthly['Month'],
            y=monthly['TotalMasIva'],
            name='Revenue',
            line=dict(color='#2E86AB', width=3)
        ))
        fig.add_trace(go.Scatter(
            x=monthly['Month'],
            y=monthly['ValorCosto'],
            name='Cost',
            line=dict(color='#C73E1D', width=3)
        ))
        fig.update_layout(height=400, hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)

    # Daily trend
    st.subheader("Daily Revenue Trend")
    daily = df.groupby('Fecha')['TotalMasIva'].sum().reset_index()

    fig = px.area(
        daily,
        x='Fecha',
        y='TotalMasIva',
        color_discrete_sequence=['#2E86AB']
    )
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)

# --------------------
# Tab 2: Customers
# --------------------
with tab2:
    st.header("Customer Analytics")

    # Customer aggregation
    customers = df.groupby('customer_name').agg({
        'TotalMasIva': ['sum', 'count', 'mean'],
        'product_name': 'nunique'
    }).reset_index()

    customers.columns = [
        'customer_name', 'total_revenue', 'orders',
        'avg_order', 'products'
    ]
    customers = customers.sort_values('total_revenue', ascending=False)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Top 20 Customers by Revenue")

        fig = px.bar(
            customers.head(20),
            x='customer_name',
            y='total_revenue',
            color='total_revenue',
            color_continuous_scale='Blues',
            hover_data=['orders', 'avg_order']
        )
        fig.update_xaxes(tickangle=-45)
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Customer Stats")
        st.metric("Total Customers", f"{len(customers):,}")
        st.metric("Avg Revenue/Customer", f"${customers['total_revenue'].mean():,.2f}")
        st.metric("Top Customer Share", f"{(customers.iloc[0]['total_revenue'] / customers['total_revenue'].sum() * 100):.1f}%")

    # Detailed table
    st.subheader("Customer Details")
    st.dataframe(
        customers.head(50),
        use_container_width=True,
        height=400
    )

# --------------------
# Tab 3: Products
# --------------------
with tab3:
    st.header("Product Performance")

    # Product aggregation
    products = df.groupby('product_name').agg({
        'TotalSinIva': 'sum',
        'ValorCosto': 'sum',
        'Cantidad': 'sum',
        'customer_name': 'nunique'
    }).reset_index()

    products.columns = [
        'product_name', 'revenue', 'cost',
        'quantity', 'customers'
    ]
    products['profit'] = products['revenue'] - products['cost']
    products['margin'] = (products['profit'] / products['revenue'] * 100).fillna(0)
    products = products.sort_values('revenue', ascending=False)

    # Apply filters
    if min_revenue > 0:
        products = products[products['revenue'] >= min_revenue]
    if show_negative_margins:
        products = products[products['margin'] < 0]

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top Products by Revenue")

        fig = px.treemap(
            products.head(20),
            path=['product_name'],
            values='revenue',
            color='margin',
            color_continuous_scale='RdYlGn',
            color_continuous_midpoint=20
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Profit Margin Distribution")

        fig = px.scatter(
            products.head(50),
            x='revenue',
            y='margin',
            size='quantity',
            color='margin',
            color_continuous_scale='RdYlGn',
            hover_data=['product_name'],
            color_continuous_midpoint=20
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

    # Detailed table
    st.subheader("Product Details")
    st.dataframe(
        products.head(100),
        use_container_width=True,
        height=400
    )

# --------------------
# Tab 4: Categories
# --------------------
with tab4:
    st.header("Category Analysis")

    # Category aggregation
    categories = df.groupby('category').agg({
        'TotalSinIva': 'sum',
        'ValorCosto': 'sum',
        'customer_name': 'count'
    }).reset_index()

    categories.columns = ['category', 'revenue', 'cost', 'orders']
    categories['profit'] = categories['revenue'] - categories['cost']
    categories['margin'] = (categories['profit'] / categories['revenue'] * 100).fillna(0)
    categories = categories.sort_values('revenue', ascending=False)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Revenue by Category")

        fig = px.pie(
            categories,
            values='revenue',
            names='category',
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.Blues_r
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Category Profit Margins")

        fig = px.bar(
            categories,
            x='category',
            y='margin',
            color='margin',
            color_continuous_scale='RdYlGn',
            color_continuous_midpoint=20
        )
        fig.update_xaxes(tickangle=-45)
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    # Category details
    st.dataframe(
        categories,
        use_container_width=True
    )

# --------------------
# Tab 5: Trends
# --------------------
with tab5:
    st.header("Trend Analysis")

    # Time-based aggregations
    df['Week'] = df['Fecha'].dt.to_period('W').astype(str)
    df['DayOfWeek'] = df['Fecha'].dt.day_name()
    df['Hour'] = df['Fecha'].dt.hour

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Weekly Trend")

        weekly = df.groupby('Week')['TotalMasIva'].sum().reset_index()

        fig = px.line(
            weekly,
            x='Week',
            y='TotalMasIva',
            markers=True,
            line_shape='spline'
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Day of Week Pattern")

        # Reorder days
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        daily_pattern = df.groupby('DayOfWeek')['TotalMasIva'].mean().reindex(day_order).reset_index()

        fig = px.bar(
            daily_pattern,
            x='DayOfWeek',
            y='TotalMasIva',
            color='TotalMasIva',
            color_continuous_scale='Blues'
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# Footer with Export Functionality
# ============================================================================

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📥 Export to Excel", use_container_width=True):
        # Create Excel file
        output = pd.ExcelWriter('business_report.xlsx', engine='openpyxl')

        df.to_excel(output, sheet_name='Raw Data', index=False)
        customers.to_excel(output, sheet_name='Customers', index=False)
        products.to_excel(output, sheet_name='Products', index=False)
        categories.to_excel(output, sheet_name='Categories', index=False)

        output.close()

        st.success("✅ Excel file generated: business_report.xlsx")

with col2:
    if st.button("📊 Download Charts", use_container_width=True):
        st.info("💡 Right-click any chart and select 'Download plot as PNG'")

with col3:
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Footer
st.markdown("---")
st.caption("Business Analytics Dashboard | Powered by Streamlit & Plotly")
