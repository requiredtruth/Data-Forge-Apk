#!/usr/bin/env python3
"""DataForge native desktop GUI (Tk, no browser)."""
from __future__ import annotations

import json
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from engine import Filter, Join, OutputColumn, ProjectDB, QueryPlan


BG="#0b1020"; PANEL="#121a2e"; PANEL2="#18223a"; INK="#e7eefc"; MUTED="#8fa3c7"
CYAN="#22d3ee"; PURPLE="#a78bfa"; GREEN="#34d399"; RED="#fb7185"; AMBER="#fbbf24"


class AskTable(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent); self.title("Create blank table"); self.configure(bg=BG); self.resizable(False, False)
        self.result=None; self.name=tk.StringVar(value="new_table")
        tk.Label(self,text="Table name",bg=BG,fg=INK).grid(row=0,column=0,sticky="w",padx=12,pady=(12,3))
        tk.Entry(self,textvariable=self.name,width=42).grid(row=1,column=0,padx=12)
        tk.Label(self,text="Columns — one per line: name, type",bg=BG,fg=INK).grid(row=2,column=0,sticky="w",padx=12,pady=(12,3))
        self.text=tk.Text(self,width=44,height=10,bg=PANEL2,fg=INK,insertbackground=INK)
        self.text.insert("1.0","id, INTEGER PRIMARY KEY\nname, TEXT\nvalue, REAL")
        self.text.grid(row=3,column=0,padx=12)
        tk.Button(self,text="Create",command=self.done,bg=CYAN,fg="#061018").grid(row=4,column=0,pady=12)
        self.transient(parent); self.grab_set(); self.wait_visibility(); self.focus_force()
    def done(self):
        cols=[]
        for line in self.text.get("1.0","end").splitlines():
            if not line.strip(): continue
            bits=[x.strip() for x in line.split(",",1)]
            cols.append((bits[0], bits[1] if len(bits)>1 else "TEXT"))
        self.result=(self.name.get(),cols); self.destroy()


class DataForge(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("DataForge — Visual Data Assembly"); self.geometry("1440x900"); self.minsize(1050,650)
        self.configure(bg=BG); self.option_add("*Font",("DejaVu Sans",10))
        self.db: ProjectDB|None=None; self.plan=QueryPlan(); self.results=([],[]); self.column_pick=None
        self.node_positions={}; self._style(); self._layout(); self.new_project(startup=True)

    def _style(self):
        s=ttk.Style(self); s.theme_use("clam")
        s.configure(".",background=BG,foreground=INK,fieldbackground=PANEL2,bordercolor="#263554")
        s.configure("TNotebook",background=BG,borderwidth=0); s.configure("TNotebook.Tab",background=PANEL,foreground=MUTED,padding=(16,8))
        s.map("TNotebook.Tab",background=[("selected",PANEL2)],foreground=[("selected",CYAN)])
        s.configure("Treeview",background=PANEL,fieldbackground=PANEL,foreground=INK,rowheight=26); s.configure("Treeview.Heading",background=PANEL2,foreground=CYAN)
        s.configure("TButton",background=PANEL2,foreground=INK,padding=7); s.map("TButton",background=[("active","#263554")])
        s.configure("Accent.TButton",background=CYAN,foreground="#07121b")

    def _layout(self):
        top=tk.Frame(self,bg="#080c18",height=54); top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top,text="◆ DATAFORGE",font=("DejaVu Sans",16,"bold"),bg="#080c18",fg=CYAN).pack(side="left",padx=16)
        for text,cmd in [("New",self.new_project),("Open",self.open_project),("Backup",self.backup),("Import",self.import_file),("Blank table",self.blank_table),("Run",self.run),("Save output",self.materialize),("Export",self.export)]:
            ttk.Button(top,text=text,command=cmd,style="Accent.TButton" if text=="Run" else "TButton").pack(side="left",padx=3,pady=8)
        self.status=tk.StringVar(value="Ready"); tk.Label(top,textvariable=self.status,bg="#080c18",fg=MUTED).pack(side="right",padx=15)
        body=tk.PanedWindow(self,orient="horizontal",bg=BG,sashwidth=5); body.pack(fill="both",expand=True)
        left=tk.Frame(body,bg=PANEL,width=235); body.add(left,minsize=190)
        tk.Label(left,text="TABLES",bg=PANEL,fg=MUTED,font=("DejaVu Sans",9,"bold")).pack(anchor="w",padx=12,pady=(12,4))
        self.tables=tk.Listbox(left,bg=PANEL,fg=INK,selectbackground="#17495b",highlightthickness=0,exportselection=False)
        self.tables.pack(fill="both",expand=True,padx=8); self.tables.bind("<<ListboxSelect>>",self.show_table_columns); self.tables.bind("<Double-1>",self.set_main)
        tk.Label(left,text="Double-click to make main table",bg=PANEL,fg=MUTED,wraplength=200).pack(pady=5)
        self.saved=tk.Listbox(left,bg=PANEL2,fg=INK,height=6,highlightthickness=0); self.saved.pack(fill="x",padx=8,pady=8); self.saved.bind("<Double-1>",self.load_saved)
        center=tk.Frame(body,bg=BG); body.add(center,minsize=570)
        self.tabs=ttk.Notebook(center); self.tabs.pack(fill="both",expand=True)
        self.flow_tab=tk.Frame(self.tabs,bg=BG); self.data_tab=tk.Frame(self.tabs,bg=BG); self.chart_tab=tk.Frame(self.tabs,bg=BG); self.sql_tab=tk.Frame(self.tabs,bg=BG)
        self.tabs.add(self.flow_tab,text="WORKSPACE"); self.tabs.add(self.data_tab,text="RESULTS"); self.tabs.add(self.chart_tab,text="CHARTS"); self.tabs.add(self.sql_tab,text="SQL")
        self.canvas=tk.Canvas(self.flow_tab,bg=BG,highlightthickness=0,scrollregion=(0,0,2400,1800)); self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<ButtonPress-2>",self.pan_start); self.canvas.bind("<B2-Motion>",self.pan_move)
        self.result_tree=ttk.Treeview(self.data_tab,show="headings"); self.result_tree.pack(fill="both",expand=True)
        self.chart=tk.Canvas(self.chart_tab,bg=BG,highlightthickness=0); self.chart.pack(fill="both",expand=True); self.chart.bind("<Configure>",lambda e:self.draw_chart())
        sqlbar=tk.Frame(self.sql_tab,bg=BG); sqlbar.pack(fill="x"); ttk.Button(sqlbar,text="Copy SQL",command=self.copy_sql).pack(side="left",padx=8,pady=8)
        self.sql=tk.Text(self.sql_tab,bg="#060914",fg=GREEN,insertbackground=INK,undo=True,font=("DejaVu Sans Mono",10)); self.sql.pack(fill="both",expand=True,padx=8,pady=(0,8))
        right=tk.Frame(body,bg=PANEL,width=310); body.add(right,minsize=270)
        tk.Label(right,text="TRANSFORM",bg=PANEL,fg=PURPLE,font=("DejaVu Sans",11,"bold")).pack(anchor="w",padx=12,pady=(12,6))
        self.main_var=tk.StringVar(); self.main_combo=ttk.Combobox(right,textvariable=self.main_var,state="readonly"); self.main_combo.pack(fill="x",padx=10); self.main_combo.bind("<<ComboboxSelected>>",lambda e:self.change_main())
        self._section(right,"JOIN LINKS",self.add_join_dialog,"+ Join")
        self.join_list=tk.Listbox(right,bg=PANEL2,fg=INK,height=5,highlightthickness=0); self.join_list.pack(fill="x",padx=10); self.join_list.bind("<Delete>",lambda e:self.delete_join())
        self._section(right,"OUTPUT COLUMNS",self.add_output,"+ Column")
        self.output_list=tk.Listbox(right,bg=PANEL2,fg=INK,height=6,highlightthickness=0); self.output_list.pack(fill="x",padx=10); self.output_list.bind("<Delete>",lambda e:self.delete_output())
        self._section(right,"FILTERS",self.add_filter,"+ Filter")
        self.filter_list=tk.Listbox(right,bg=PANEL2,fg=INK,height=6,highlightthickness=0); self.filter_list.pack(fill="x",padx=10); self.filter_list.bind("<Delete>",lambda e:self.delete_filter())
        opts=tk.Frame(right,bg=PANEL); opts.pack(fill="x",padx=10,pady=10)
        self.distinct=tk.BooleanVar(); ttk.Checkbutton(opts,text="Remove duplicates",variable=self.distinct,command=self.sync_plan).pack(anchor="w")
        tk.Label(opts,text="Row limit",bg=PANEL,fg=MUTED).pack(side="left"); self.limit=tk.StringVar(value="1000"); tk.Entry(opts,textvariable=self.limit,bg=PANEL2,fg=INK,width=9).pack(side="left",padx=6)
        ttk.Button(right,text="Save query",command=self.save_query).pack(fill="x",padx=10,pady=4)

    def _section(self,parent,title,cmd,button):
        row=tk.Frame(parent,bg=PANEL); row.pack(fill="x",padx=10,pady=(12,3)); tk.Label(row,text=title,bg=PANEL,fg=MUTED,font=("DejaVu Sans",8,"bold")).pack(side="left"); ttk.Button(row,text=button,command=cmd).pack(side="right")

    def new_project(self,startup=False):
        if startup:
            path=Path.home()/"DataForge"/"default.dataforge.sqlite"; path.parent.mkdir(parents=True,exist_ok=True)
        else:
            p=filedialog.asksaveasfilename(defaultextension=".dataforge.sqlite",filetypes=[("DataForge project","*.dataforge.sqlite"),("SQLite","*.sqlite")]);
            if not p:return
            path=Path(p)
        if self.db:self.db.close()
        self.db=ProjectDB(path); self.plan=QueryPlan(); self.refresh(); self.status.set(str(path))

    def open_project(self):
        p=filedialog.askopenfilename(filetypes=[("SQLite/DataForge","*.sqlite *.db *.dataforge.sqlite"),("All files","*")]);
        if not p:return
        if self.db:self.db.close()
        self.db=ProjectDB(p); self.plan=QueryPlan(); self.refresh(); self.status.set(p)

    def backup(self):
        if not self.db:return
        p=filedialog.asksaveasfilename(defaultextension=".sqlite",initialfile=self.db.path.stem+"_backup.sqlite")
        if p:self.db.conn.commit(); shutil.copy2(self.db.path,p); self.status.set("Backup saved")

    def import_file(self):
        p=filedialog.askopenfilename(filetypes=[("Data files","*.csv *.tsv *.json"),("CSV","*.csv *.tsv"),("JSON","*.json")]);
        if not p:return
        try:
            result=self.db.import_json(p) if p.lower().endswith(".json") else self.db.import_csv(p)
            self.refresh(); self.status.set(f"Imported {result[1]:,} rows into {result[0]}")
            if not self.plan.main_table:self.plan.main_table=result[0];self.refresh()
        except Exception as e:messagebox.showerror("Import failed",str(e))

    def blank_table(self):
        d=AskTable(self)
        if d.result:
            try:self.db.create_table(*d.result);self.refresh()
            except Exception as e:messagebox.showerror("Create table",str(e))

    def refresh(self):
        names=self.db.tables() if self.db else []
        self.tables.delete(0,"end"); [self.tables.insert("end",x) for x in names]
        self.main_combo["values"]=names; self.main_var.set(self.plan.main_table)
        self.saved.delete(0,"end"); [self.saved.insert("end",x) for x in (self.db.saved_plans() if self.db else [])]
        self.refresh_lists(); self.draw_flow(); self.update_sql()

    def set_main(self,e=None):
        s=self.tables.curselection()
        if s:self.plan.main_table=self.tables.get(s[0]);self.main_var.set(self.plan.main_table);self.plan.joins=[];self.refresh()
    def change_main(self):self.plan.main_table=self.main_var.get();self.plan.joins=[];self.refresh()
    def show_table_columns(self,e=None):
        s=self.tables.curselection()
        if s:self.status.set(f"{self.tables.get(s[0])}: {len(self.db.columns(self.tables.get(s[0])))} columns")

    def available_refs(self):
        tabs=[self.plan.main_table]+[j.table for j in self.plan.joins]
        return [f"{t}.{c['name']}" for t in tabs if t for c in self.db.columns(t)]

    def ask_choice(self,title,prompt,values):
        win=tk.Toplevel(self);win.title(title);win.configure(bg=BG);win.transient(self);win.grab_set();out=[]
        tk.Label(win,text=prompt,bg=BG,fg=INK).pack(padx=15,pady=(15,5));v=tk.StringVar(value=values[0] if values else "");c=ttk.Combobox(win,textvariable=v,values=values,width=45);c.pack(padx=15,pady=5)
        ttk.Button(win,text="OK",command=lambda:(out.append(v.get()),win.destroy())).pack(pady=12);self.wait_window(win);return out[0] if out else None

    def add_join_dialog(self):
        if not self.plan.main_table:return messagebox.showinfo("Join","Choose a main table first")
        tables=[x for x in self.db.tables() if x!=self.plan.main_table and x not in [j.table for j in self.plan.joins]]
        table=self.ask_choice("Add join","Table to join",tables)
        if not table:return
        left=self.ask_choice("Add join","Existing-side column",self.available_refs())
        right=self.ask_choice("Add join","Joined-table column",[f"{table}.{c['name']}" for c in self.db.columns(table)])
        kind=self.ask_choice("Add join","Join type",["LEFT","INNER","CROSS"])
        if left and right and kind:self.plan.joins.append(Join(table,left,right,kind));self.refresh()

    def pick_column(self,table,col):
        ref=f"{table}.{col}"
        if not self.plan.main_table:
            self.plan.main_table=table; self.main_var.set(table); self.refresh(); return
        if self.column_pick is None:self.column_pick=ref;self.status.set(f"Join start: {ref}. Click a column in another table.");return
        first=self.column_pick;self.column_pick=None
        t1=first.split(".",1)[0];t2=table
        if t1==t2:return self.status.set("Join columns must come from different tables")
        existing=[self.plan.main_table]+[j.table for j in self.plan.joins]
        new=t2 if t2 not in existing else t1 if t1 not in existing else None
        if not new:return self.status.set("Those tables are already connected")
        left,right=(first,ref) if new==t2 else (ref,first)
        self.plan.joins.append(Join(new,left,right,"LEFT"));self.refresh()

    def add_output(self):
        ref=self.ask_choice("Output column","Column",self.available_refs());
        if not ref:return
        agg=self.ask_choice("Output column","Aggregation",["","COUNT","SUM","AVG","MIN","MAX","GROUP_CONCAT"])
        alias=simpledialog.askstring("Output column","Rename output (optional)",parent=self) or ""
        self.plan.columns.append(OutputColumn(ref,alias,agg or ""));self.refresh()
    def add_filter(self):
        ref=self.ask_choice("Filter","Column",self.available_refs());
        if not ref:return
        op=self.ask_choice("Filter","Operator",["=","!=",">",">=","<","<=","LIKE","NOT LIKE","IS NULL","IS NOT NULL","IN"])
        val="" if op in ("IS NULL","IS NOT NULL") else simpledialog.askstring("Filter","Value (IN uses comma-separated values)",parent=self)
        if op:self.plan.filters.append(Filter(ref,op,val or ""));self.refresh()
    def delete_join(self):
        s=self.join_list.curselection();
        if s:self.plan.joins.pop(s[0]);self.refresh()
    def delete_output(self):
        s=self.output_list.curselection();
        if s:self.plan.columns.pop(s[0]);self.refresh()
    def delete_filter(self):
        s=self.filter_list.curselection();
        if s:self.plan.filters.pop(s[0]);self.refresh()

    def refresh_lists(self):
        self.join_list.delete(0,"end");[self.join_list.insert("end",f"{j.kind} {j.table}: {j.left} = {j.right}") for j in self.plan.joins]
        self.output_list.delete(0,"end");[self.output_list.insert("end",f"{c.aggregate+' ' if c.aggregate else ''}{c.expression}{' → '+c.alias if c.alias else ''}") for c in self.plan.columns]
        self.filter_list.delete(0,"end");[self.filter_list.insert("end",f"{f.column} {f.operator} {f.value}") for f in self.plan.filters]
        self.distinct.set(self.plan.distinct);self.limit.set(str(self.plan.limit))

    def sync_plan(self):
        self.plan.distinct=self.distinct.get()
        try:self.plan.limit=int(self.limit.get())
        except ValueError:self.plan.limit=1000
        self.update_sql()

    def update_sql(self):
        self.sync_plan_values()
        try:sql,params=self.plan.sql_and_params();text=sql+("\n\n-- Parameters: "+repr(params) if params else "")
        except Exception as e:text="-- "+str(e)
        self.sql.delete("1.0","end");self.sql.insert("1.0",text)
    def sync_plan_values(self):
        self.plan.distinct=self.distinct.get() if hasattr(self,"distinct") else False
        try:self.plan.limit=int(self.limit.get())
        except Exception:self.plan.limit=1000

    def run(self):
        self.sync_plan_values()
        try:
            self.results=self.db.execute_plan(self.plan);self.show_results();self.update_sql();self.draw_chart();self.tabs.select(self.data_tab);self.status.set(f"{len(self.results[1]):,} result rows")
        except Exception as e:messagebox.showerror("Query failed",str(e))

    def show_results(self):
        cols,rows=self.results;self.result_tree.delete(*self.result_tree.get_children());self.result_tree["columns"]=list(range(len(cols)))
        for i,c in enumerate(cols):self.result_tree.heading(i,text=c);self.result_tree.column(i,width=140,stretch=True)
        for row in rows[:5000]:self.result_tree.insert("", "end", values=["" if x is None else x for x in row])

    def materialize(self):
        if not self.plan.main_table:return
        name=simpledialog.askstring("Save output","New SQLite table name",initialvalue="assembled_output",parent=self)
        if name:
            try:name=self.db.materialize(self.plan,name);self.refresh();self.status.set(f"Saved work result as table: {name}")
            except Exception as e:messagebox.showerror("Save output",str(e))

    def export(self):
        if not self.results[0]:self.run()
        if not self.results[0]:return
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv"),("JSON","*.json")]);
        if p:self.db.export_rows(*self.results,p);self.status.set(f"Exported {len(self.results[1]):,} rows")

    def save_query(self):
        name=simpledialog.askstring("Save query","Query name",initialvalue=self.plan.name,parent=self)
        if name:self.plan.name=name;self.db.save_plan(self.plan);self.refresh()
    def load_saved(self,e=None):
        s=self.saved.curselection()
        if s:self.plan=self.db.load_plan(self.saved.get(s[0]));self.refresh()
    def copy_sql(self):self.clipboard_clear();self.clipboard_append(self.sql.get("1.0","end-1c"));self.status.set("SQL copied")

    def draw_flow(self):
        self.canvas.delete("all")
        names=self.db.tables() if self.db else []
        for i,t in enumerate(names):
            x=35+(i%3)*285;y=35+(i//3)*310;cols=self.db.columns(t);active=t==self.plan.main_table or t in [j.table for j in self.plan.joins]
            color=CYAN if t==self.plan.main_table else PURPLE if active else "#334155"
            self.canvas.create_rectangle(x,y,x+245,y+50+min(len(cols),9)*25,fill=PANEL,outline=color,width=2,tags=("node",t))
            self.canvas.create_rectangle(x,y,x+245,y+38,fill=PANEL2,outline=color,width=1)
            self.canvas.create_text(x+12,y+19,text=("MAIN  " if t==self.plan.main_table else "")+t,anchor="w",fill=color,font=("DejaVu Sans",10,"bold"))
            for n,c in enumerate(cols[:9]):
                cy=y+50+n*25;self.canvas.create_oval(x+8,cy-4,x+16,cy+4,fill=color,outline="")
                item=self.canvas.create_text(x+25,cy,text=f"{c['name']}   {c['type']}",anchor="w",fill=INK)
                self.canvas.tag_bind(item,"<Button-1>",lambda e,tt=t,cc=c['name']:self.pick_column(tt,cc))
            if len(cols)>9:self.canvas.create_text(x+25,y+50+9*25,text=f"+ {len(cols)-9} more",anchor="w",fill=MUTED)
        for j in self.plan.joins:
            tabs=names; a=tabs.index(j.left.split('.',1)[0]);b=tabs.index(j.table)
            ax=35+(a%3)*285+245;ay=35+(a//3)*310+20;bx=35+(b%3)*285;by=35+(b//3)*310+20
            self.canvas.create_line(ax,ay,bx,by,fill=GREEN,width=3,arrow="last",smooth=True)
    def pan_start(self,e):self.canvas.scan_mark(e.x,e.y)
    def pan_move(self,e):self.canvas.scan_dragto(e.x,e.y,gain=1)

    def draw_chart(self):
        self.chart.delete("all");cols,rows=self.results
        if len(cols)<2 or not rows:self.chart.create_text(30,30,text="Run a result with a category column and numeric column.",anchor="nw",fill=MUTED);return
        numeric=None
        for i in range(1,len(cols)):
            try:[float(r[i]) for r in rows[:50] if r[i] is not None];numeric=i;break
            except (ValueError,TypeError):pass
        if numeric is None:return
        data=[]
        for r in rows[:30]:
            try:data.append((str(r[0]),float(r[numeric] or 0)))
            except (ValueError,TypeError):pass
        if not data:return
        w=max(self.chart.winfo_width(),600);h=max(self.chart.winfo_height(),400);m=55;mx=max(abs(v) for _,v in data) or 1;bw=max(8,(w-2*m)/len(data)-8)
        self.chart.create_text(m,18,text=f"{cols[numeric]} by {cols[0]}",anchor="w",fill=CYAN,font=("DejaVu Sans",14,"bold"))
        for i,(label,val) in enumerate(data):
            x=m+i*(w-2*m)/len(data);bh=(h-120)*abs(val)/mx;y=h-65-bh
            self.chart.create_rectangle(x,y,x+bw,h-65,fill=PURPLE,outline="");self.chart.create_text(x+bw/2,y-10,text=f"{val:g}",fill=INK)
            self.chart.create_text(x+bw/2,h-55,text=label[:12],angle=35,anchor="ne",fill=MUTED)


if __name__=="__main__": DataForge().mainloop()
