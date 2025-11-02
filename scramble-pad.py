#!/usr/bin/env python3
"""
Scramble Pad Trainer

Tiny desktop app to practise entering a fixed 4-digit PIN on a scrambled keypad.
Keyboard input is by *position* (like a numpad / phone keypad), not by the digit
printed on the key. Clicks work too. Tracks speed/accuracy to a CSV for bragging
rights or self-loathing, depending on the day.
"""
from __future__ import annotations
import csv, random, time, configparser, statistics, tkinter as tk
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from tkinter import messagebox

APP_TITLE = "Scramble Pad Trainer"
CONF_FILE = Path(__file__).with_name("scramblepad.conf")
STATS_FILE = Path(__file__).with_name("scramblepad_stats.csv")

@dataclass
class RoundResult:
    # One round = one attempt to enter the PIN
    duration_ms:int
    correct:int
    total:int
    @property
    def accuracy_pct(self): return 100.0*self.correct/max(1,self.total)

def load_or_create_pin():
    """
    Grab a 4-digit PIN from scramblepad.conf. If missing/invalid, create one.
    I’m not storing state anywhere clever—local file is fine for this.
    """
    cfg=configparser.ConfigParser()
    if CONF_FILE.exists():
        cfg.read(CONF_FILE)
        pin=cfg.get("settings","pin",fallback="")
        if pin.isdigit() and len(pin)==4: return pin
    # Fall back to a new random PIN and persist it for next time.
    pin=f"{random.randint(0,9999):04d}"
    cfg["settings"]={"pin":pin}
    with open(CONF_FILE,"w",encoding="utf-8") as f: cfg.write(f)
    return pin

def append_stats(result:RoundResult):
    """
    Append the latest result to a CSV with a header if it's the first run.
    Keeping it simple: timestamp, duration, accuracy, correct/total.
    """
    hdr=["timestamp","duration_ms","accuracy_pct","correct","total"]
    row=[datetime.now().isoformat(timespec="seconds"),result.duration_ms,f"{result.accuracy_pct:.2f}",result.correct,result.total]
    new=not STATS_FILE.exists()
    with open(STATS_FILE,"a",newline="",encoding="utf-8") as f:
        w=csv.writer(f)
        if new:w.writerow(hdr)
        w.writerow(row)

def read_stats_last_n(n=50):
    """
    Read the last N rows from the CSV. If the file doesn’t exist yet, shrug.
    Any malformed rows are quietly skipped because life is short.
    """
    if not STATS_FILE.exists(): return []
    rows=[]
    with open(STATS_FILE,newline="",encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try: rows.append({"timestamp":row["timestamp"],"duration_ms":int(row["duration_ms"]),"accuracy_pct":float(row["accuracy_pct"]),"correct":int(row["correct"]),"total":int(row["total"])} )
            except: pass
    return rows[-n:]

class ScramblePad(tk.Tk):
    """
    Tkinter app:
    - 3x3 grid plus a bottom-middle '0' (i.e., phone/numpad layout)
    - Digits are shuffled each round, but *positions* stay fixed
    - Keyboard entries use positions (7/8/9 is the top row, etc.)
    """
    def __init__(self,pin:str):
        super().__init__()
        self.title(APP_TITLE)
        self.configure(padx=14,pady=14,bg="#1a1a1a")
        self.pin=pin; self.pin_len=len(pin)
        self.entry=[]; self.inputs=[]; self.started_at=None
        # keypad positional mappings
        self.NUMPAD_MAP={"KP_7":(0,0),"KP_8":(0,1),"KP_9":(0,2),"KP_4":(1,0),"KP_5":(1,1),"KP_6":(1,2),"KP_1":(2,0),"KP_2":(2,1),"KP_3":(2,2),"KP_0":(3,1)}
        self.KEYPOS_MAP={"1":(2,0),"2":(2,1),"3":(2,2),"4":(1,0),"5":(1,1),"6":(1,2),"7":(0,0),"8":(0,1),"9":(0,2),"0":(3,1)}
        self.build_ui(); self.shuffle_digits(); self.bind_all("<Key>",self.on_key)

    def build_ui(self):
        # Minimal styling. Dark mode because… of course.
        outer=tk.Frame(self,bg="#1a1a1a"); outer.grid(row=0,column=0)
        self.display=tk.Label(outer,text="Use keyboard as POSITIONS (like numpad) or click cells.",fg="#e6e6e6",bg="#1a1a1a",font=("Segoe UI",12))
        self.display.grid(row=0,column=0,columnspan=3,pady=(0,10))
        self.grid_frame=tk.Frame(outer,bg="#0f0f0f",bd=4); self.grid_frame.grid(row=1,column=0)
        self.cells=[]
        for r in range(4):
            for c in range(3):
                b=tk.Button(self.grid_frame,text="",width=4,height=2,font=("Consolas",20,"bold"),fg="#ff3d3d",bg="#101010",activebackground="#262626",relief=tk.RIDGE,bd=2,command=lambda br=r,bc=c:self.on_click_cell(br,bc))
                b.grid(row=r,column=c,padx=2,pady=2,sticky="nsew"); self.cells.append(b)
        ctrl=tk.Frame(outer,bg="#1a1a1a"); ctrl.grid(row=2,column=0,pady=(10,0))
        tk.Button(ctrl,text="START",width=10,command=self.start_round).grid(row=0,column=0,padx=4)
        tk.Button(ctrl,text="CLEAR",width=10,command=self.clear_entry).grid(row=0,column=1,padx=4)
        tk.Button(ctrl,text="STATS (S)",width=10,command=self.show_stats).grid(row=0,column=2,padx=4)
        self.entry_label=tk.Label(outer,text="",fg="#cfcfcf",bg="#1a1a1a",font=("Consolas",14))
        self.entry_label.grid(row=3,column=0,pady=(10,0))

    def shuffle_digits(self):
        """
        Randomise which digit is printed in each cell, but keep coordinates stable.
        The trick is that you *enter by position*, so your muscle memory is tested.
        """
        digits=[str(d) for d in range(10)]; random.shuffle(digits)
        positions=[(r,c) for r in range(3) for c in range(3)]+[(3,1)]
        self.coord_to_digit={}; self.digit_to_coord={}
        for idx,(r,c) in enumerate(positions):
            d=digits[idx]; i=r*3+c; btn=self.cells[i]; btn.config(text=d)
            self.coord_to_digit[(r,c)]=d; self.digit_to_coord[d]=(r,c)

    def start_round(self):
        """
        Reset state and reshuffle the board. Fresh hell, fresh hope.
        """
        self.entry.clear()
        self.inputs.clear()
        self.started_at=None
        self.entry_label.config(text="")
        self.display.config(text="Follow the grid layout visually.")
        self.shuffle_digits()

    def clear_entry(self): 
        """
        Panic button: wipe current attempt without reshuffling.
        """
        self.entry.clear()
        self.inputs.clear()
        self.started_at=None
        self.entry_label.config(text="")

    def on_click_cell(self,r,c):
        """
        Mouse click handler: accept the digit currently printed at r,c.
        We still store the *digit* we saw, because that’s what we’ll compare to the PIN.
        """
        d=self.coord_to_digit.get((r,c))
        if d:
            self.accept_digit(d); self.inputs.append(f"btn({r},{c})")

    def on_key(self,event):
        """
        Keyboard handler. Important bits:
        - Enter/KP_Enter finishes early if you’ve decided you’re done lying to yourself.
        - Backspace clears.
        - Number keys and numpad keys map to *positions*, not digits.
        - 'S' pops stats because I will absolutely forget the button exists.
        """
        k=event.keysym
        if k in {"Return","KP_Enter"}: self.finish_if_ready(True); return
        if k=="BackSpace": self.clear_entry(); return
        if k in self.NUMPAD_MAP:
            coord=self.NUMPAD_MAP[k]; d=self.coord_to_digit.get(coord)
            if d: self.accept_digit(d); self.inputs.append(k); return
        if k in self.KEYPOS_MAP:
            coord=self.KEYPOS_MAP[k]; d=self.coord_to_digit.get(coord)
            if d: self.accept_digit(d); self.inputs.append(k); return
        if k.lower()=="s": self.show_stats()

    def accept_digit(self,d:str):
        """
        Accept one digit (the digit printed in the cell at the chosen position).
        Start the timer on first input. Mask the entry as dots. Finish if we’re at length.
        """
        if self.started_at is None: self.started_at=time.perf_counter()
        if len(self.entry)>=self.pin_len: return
        self.entry.append(d); self.entry_label.config(text="•"*len(self.entry)); self.finish_if_ready()

    def finish_if_ready(self,force=False):
        """
        If we’ve got enough digits (or been told to stop), compute the result:
        - Duration from first keypress/click
        - How many digits matched the configured PIN in the correct positions
        Then save stats, show a friendly verdict, and reshuffle for the next go.
        """
        if not self.entry: return
        if not force and len(self.entry)<self.pin_len: return
        dur=int(1000*(time.perf_counter()-(self.started_at or time.perf_counter())))
        entered=(self.entry+[""]*self.pin_len)[:self.pin_len]
        correct=sum(1 for i,ch in enumerate(entered) if ch==self.pin[i])
        res=RoundResult(dur,correct,self.pin_len)
        append_stats(res); self.show_result(res); self.start_round()

    def show_result(self,res:RoundResult):
        """
        Modal popup with the verdict, what we typed (keys/clicks), the interpreted
        digits, and the usual time/accuracy readout. Enough info to debug fat-finger syndrome.
        """
        interpreted="".join(self.entry[:self.pin_len])
        verdict="Correct" if interpreted==self.pin else "Incorrect"
        messagebox.showinfo("Result",f"{verdict}\n\nPIN: {self.pin}\nEntered: {interpreted}\n\nTime: {res.duration_ms} ms\nAccuracy: {res.accuracy_pct:.0f}% ({res.correct}/{res.total})",parent=self)

    def show_stats(self):
        """
        Lightweight stats: all-time averages, last-10 trend, and latest result.
        This is not Power BI; it’s a nudge to see if you’re actually improving.
        """
        rows=read_stats_last_n(100)
        if not rows: messagebox.showinfo("Stats","No stats yet.",parent=self); return
        last10=rows[-10:]
        avg_t=statistics.fmean(r["duration_ms"] for r in rows)
        avg_a=statistics.fmean(r["accuracy_pct"] for r in rows)
        last_t=statistics.fmean(r["duration_ms"] for r in last10)
        last_a=statistics.fmean(r["accuracy_pct"] for r in last10)
        msg=(f"Results stored: {len(rows)}\n\nAll-time avg: {avg_t:.0f} ms, {avg_a:.1f}%\nLast 10 avg: {last_t:.0f} ms, {last_a:.1f}%\nLatest: {rows[-1]['timestamp']} ({rows[-1]['duration_ms']} ms, {rows[-1]['accuracy_pct']:.0f}%)")
        messagebox.showinfo("Stats",msg,parent=self)

def main():
    pin=load_or_create_pin(); app=ScramblePad(pin); app.mainloop()
if __name__=="__main__": main()