import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from inventory import get_stock_valuation

class StockChart(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Stock Chart")
        self.geometry("600x400")

        data, _ = get_stock_valuation()
        items = [d["Item"] for d in data]
        values = [d["Value"] for d in data]

        fig = Figure(figsize=(6,4))
        ax = fig.add_subplot(111)
        ax.bar(items, values)
        ax.set_title("Stock Valuation")
        ax.set_ylabel("Value")

        canvas = FigureCanvasTkAgg(fig, self)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
