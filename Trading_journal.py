import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
import base64
from io import BytesIO
import numpy as np

# Initialize session state
if 'trades' not in st.session_state:
    st.session_state.trades = pd.DataFrame(columns=[
        "Date", "Type", "R_Value", "Amount", "Image", "Notes"
    ])

# Page config
st.set_page_config(layout="wide", page_title="Trading Journal")
st.title("📈 Advanced Trading Journal")

# ====== SIDEBAR - TRADE INPUT ======
with st.sidebar:
    st.header("➕ Add New Trade")
    
    with st.form("trade_form", clear_on_submit=True):
        # Trade type and R value
        col1, col2 = st.columns(2)
        trade_type = col1.selectbox("Trade Type", ["W2R", "W1R", "L1R", "L2R", "Custom $"])
        r_value = col2.number_input("R Value ($)", min_value=0.01, value=None, placeholder="Enter R", step=0.01)
        
        # Amount calculation
        if trade_type == "Custom $":
            amount = st.number_input("P&L ($)", step=0.01)
        else:
            if r_value is None:
                amount = None
                st.warning("Enter R value to calculate P&L")
            else:
                multiplier = float(trade_type[1:-1])
                amount = multiplier * r_value if trade_type.startswith("W") else -multiplier * r_value
                st.info(f"Calculated P&L: ${amount:.2f}")
        
        # Date and attachments
        trade_date = st.date_input("Date", date.today())
        uploaded_image = st.file_uploader("Attach Image", type=["png", "jpg", "jpeg"])
        notes = st.text_area("Notes")
        
        submitted = st.form_submit_button("Save Trade")
        
        if submitted:
            if (trade_type != "Custom $" and r_value is None) or amount is None:
                st.error("Please enter all required fields")
            else:
                # Handle image upload
                img_str = None
                if uploaded_image:
                    img_bytes = uploaded_image.read()
                    img_str = base64.b64encode(img_bytes).decode()
                
                # Add to trades
                new_trade = pd.DataFrame([{
                    "Date": trade_date,
                    "Type": trade_type,
                    "R_Value": r_value,
                    "Amount": amount,
                    "Image": img_str,
                    "Notes": notes
                }])
                
                st.session_state.trades = pd.concat(
                    [st.session_state.trades, new_trade], 
                    ignore_index=True
                )
                st.success("Trade saved!")

# ====== MAIN DASHBOARD ======
if st.session_state.trades.empty:
    st.info("No trades recorded yet. Add your first trade in the sidebar!")
else:
    # Convert to datetime for filtering
    df = st.session_state.trades.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date")
    
    # Calculate cumulative metrics
    df["Cumulative_PnL"] = df["Amount"].cumsum()
    df["Daily_PnL"] = df.groupby("Date")["Amount"].transform("sum")
    
    # ====== TIME FILTERS ======
    st.header("🔍 Time Filters")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        show_all = st.checkbox("Show All Data", True)
    
    if not show_all:
        with col2:
            time_filter = st.selectbox("Filter By", ["Weekly", "Monthly", "Quarterly", "Custom Range"])
        
        with col3:
            if time_filter == "Weekly":
                selected_week = st.selectbox("Select Week", 
                    sorted(df["Date"].dt.to_period("W").unique(), reverse=True)
                filtered_df = df[df["Date"].dt.to_period("W") == selected_week]
            
            elif time_filter == "Monthly":
                selected_month = st.selectbox("Select Month", 
                    sorted(df["Date"].dt.to_period("M").unique(), reverse=True)
                filtered_df = df[df["Date"].dt.to_period("M") == selected_month]
            
            elif time_filter == "Quarterly":
                selected_quarter = st.selectbox("Select Quarter", 
                    sorted(df["Date"].dt.to_period("Q").unique(), reverse=True)
                filtered_df = df[df["Date"].dt.to_period("Q") == selected_quarter]
            
            else:  # Custom Range
                date_range = st.date_input("Select Date Range", 
                    [df["Date"].min(), df["Date"].max()])
                if len(date_range) == 2:
                    filtered_df = df[
                        (df["Date"] >= pd.to_datetime(date_range[0])) & 
                        (df["Date"] <= pd.to_datetime(date_range[1]))
                else:
                    filtered_df = df
    else:
        filtered_df = df
    
    # ====== METRICS CALCULATION ======
    st.header("📊 Performance Metrics")
    
    if not filtered_df.empty:
        # Basic stats
        total_trades = len(filtered_df)
        winning_trades = len(filtered_df[filtered_df["Amount"] > 0])
        losing_trades = len(filtered_df[filtered_df["Amount"] < 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        total_wins = filtered_df[filtered_df["Amount"] > 0]["Amount"].sum()
        total_losses = abs(filtered_df[filtered_df["Amount"] < 0]["Amount"].sum())
        
        profit_factor = total_wins / total_losses if total_losses > 0 else np.inf
        avg_win = total_wins / winning_trades if winning_trades > 0 else 0
        avg_loss = total_losses / losing_trades if losing_trades > 0 else 0
        expectancy = (avg_win * win_rate) + (-avg_loss * (1 - win_rate))
        
        # Drawdown calculation
        cumulative = filtered_df["Amount"].cumsum()
        peak = cumulative.expanding(min_periods=1).max()
        drawdown = (cumulative - peak)
        max_drawdown = drawdown.min()
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Trades", total_trades)
        col2.metric("Win Rate", f"{win_rate:.1%}")
        col3.metric("Profit Factor", f"{profit_factor:.2f}")
        col4.metric("Expectancy", f"${expectancy:.2f}")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Avg Win", f"${avg_win:.2f}")
        col2.metric("Avg Loss", f"${avg_loss:.2f}")
        col3.metric("Max Drawdown", f"${max_drawdown:.2f}")
        col4.metric("Net P&L", f"${filtered_df['Amount'].sum():.2f}")
        
        # ====== CHARTS ======
        st.header("📈 Performance Visualization")
        
        # Daily Candlestick Chart
        daily_df = filtered_df.groupby("Date").agg({
            "Amount": ["min", "max", "first", "last"]
        }).reset_index()
        daily_df.columns = ["Date", "Low", "High", "Open", "Close"]
        
        fig1 = go.Figure(data=[go.Candlestick(
            x=daily_df["Date"],
            open=daily_df["Open"],
            high=daily_df["High"],
            low=daily_df["Low"],
            close=daily_df["Close"],
            name="Daily P&L"
        )])
        fig1.update_layout(title="Daily P&L (Candlestick)", xaxis_title="Date", yaxis_title="Amount ($)")
        st.plotly_chart(fig1, use_container_width=True)
        
        # Cumulative P&L Line Chart
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=filtered_df["Date"],
            y=filtered_df["Cumulative_PnL"],
            mode="lines",
            name="Cumulative P&L"
        ))
        fig2.update_layout(title="Cumulative P&L", xaxis_title="Date", yaxis_title="Amount ($)")
        st.plotly_chart(fig2, use_container_width=True)
        
        # ====== TRADE HISTORY ======
        st.header("📋 Trade History")
        
        # Convert image data for display
        display_df = filtered_df.copy()
        display_df["Image"] = display_df["Image"].apply(
            lambda x: "📷" if x else None
        )
        
        # Show dataframe with clickable images
        st.dataframe(
            display_df[["Date", "Type", "R_Value", "Amount", "Image", "Notes"]].sort_values("Date", ascending=False),
            use_container_width=True
        )
        
        # Image preview when clicked
        selected_indices = st.session_state.get("selected_indices", [])
        if len(selected_indices) > 0:
            selected_trade = filtered_df.iloc[selected_indices[0]]
            if selected_trade["Image"]:
                st.image(BytesIO(base64.b64decode(selected_trade["Image"])), 
                        caption=f"Trade on {selected_trade['Date'].strftime('%Y-%m-%d')}")
        
        # ====== DATA EXPORT ======
        st.header("💾 Data Management")
        csv = df.to_csv(index=False).encode()
        st.download_button(
            label="Export All Trades (CSV)",
            data=csv,
            file_name="trading_journal.csv",
            mime="text/csv"
        )
        
        if st.button("Clear All Trades"):
            st.session_state.trades = pd.DataFrame(columns=[
                "Date", "Type", "R_Value", "Amount", "Image", "Notes"
            ])
            st.rerun()
    else:
        st.warning("No trades found in selected time period")
