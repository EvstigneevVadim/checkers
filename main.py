import tkinter as tk
from tkinter import messagebox,ttk
import json,os,random,hashlib,base64,hmac
N,CELL=10,64
LIGHT,DARK="#EEEED2","#769656"
SEL_OUT,MOVE_OUT,CAP_OUT="#4A90E2","#F5A623","#7ED321"
DIRS=[(-1,-1),(-1,1),(1,-1),(1,1)]
PBKDF2_ITERS=120_000
BASE_DIR=os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
USERS_FILE=os.path.join(BASE_DIR,"users.json")
def _b64e(b):return base64.b64encode(b).decode("ascii")
def _b64d(s):return base64.b64decode(s.encode("ascii"))
def inside(r,c):return 0<=r<N and 0<=c<N
def copy_board(b):return [row[:] for row in b]
def load_users():
    if not os.path.exists(USERS_FILE):return {}
    try:
        with open(USERS_FILE,"r",encoding="utf-8") as f:data=json.load(f)
        return data if isinstance(data,dict) else {}
    except Exception:return {}
def save_users(u):
    with open(USERS_FILE,"w",encoding="utf-8") as f:json.dump(u,f,ensure_ascii=False,indent=2)
def hash_password(pw,salt=None):
    salt=os.urandom(16) if salt is None else salt
    dk=hashlib.pbkdf2_hmac("sha256",pw.encode("utf-8"),salt,PBKDF2_ITERS)
    return _b64e(salt),_b64e(dk)
def verify_password(pw,salt_b64,hash_b64):
    salt=_b64d(salt_b64);_,dk=hash_password(pw,salt)
    return hmac.compare_digest(dk,hash_b64)
def init_board():
    b=[[0]*N for _ in range(N)]
    for r in range(0,4):
        for c in range(N):
            if (r+c)%2:b[r][c]=-1
    for r in range(6,10):
        for c in range(N):
            if (r+c)%2:b[r][c]=1
    return b
def count_pieces(b):
    w=bl=0
    for r in range(N):
        for c in range(N):
            p=b[r][c]
            if p>0:w+=1
            elif p<0:bl+=1
    return w,bl
def man_caps(b,r,c,color):
    piece=b[r][c];res=[]
    def dfs(brd,pr,pc,steps):
        found=False
        for dr,dc in DIRS:
            r1,c1=pr+dr,pc+dc; r2,c2=pr+2*dr,pc+2*dc
            if not inside(r2,c2) or brd[r2][c2]!=0:continue
            if not inside(r1,c1) or brd[r1][c1]*color>=0:continue
            found=True;nb=copy_board(brd)
            nb[pr][pc]=0;nb[r1][c1]=0;nb[r2][c2]=piece
            dfs(nb,r2,c2,steps+[{"to":(r2,c2),"cap":(r1,c1)}])
        if (not found) and steps:res.append(steps)
    dfs(b,r,c,[]);return res
def king_caps(b,r,c,color):
    piece=b[r][c];res=[]
    def dfs(brd,pr,pc,steps):
        found=False
        for dr,dc in DIRS:
            rr,cc=pr+dr,pc+dc
            while inside(rr,cc) and brd[rr][cc]==0:rr+=dr;cc+=dc
            if not inside(rr,cc) or brd[rr][cc]*color>0:continue
            cap_r,cap_c=rr,cc; lr,lc=cap_r+dr,cap_c+dc
            while inside(lr,lc) and brd[lr][lc]==0:
                found=True;nb=copy_board(brd)
                nb[pr][pc]=0;nb[cap_r][cap_c]=0;nb[lr][lc]=piece
                dfs(nb,lr,lc,steps+[{"to":(lr,lc),"cap":(cap_r,cap_c)}])
                lr+=dr;lc+=dc
        if (not found) and steps:res.append(steps)
    dfs(b,r,c,[]);return res
def gen_moves(b,color):
    caps=[];norms=[]
    for r in range(N):
        for c in range(N):
            p=b[r][c]
            if p*color<=0:continue
            if abs(p)==1:
                seqs=man_caps(b,r,c,color)
                for s in seqs:caps.append({"from":(r,c),"steps":s,"capN":len(s)})
                if not seqs:
                    dr=-1 if color==1 else 1
                    for dc in (-1,1):
                        nr,nc=r+dr,c+dc
                        if inside(nr,nc) and b[nr][nc]==0:norms.append({"from":(r,c),"steps":[{"to":(nr,nc),"cap":None}],"capN":0})
            else:
                seqs=king_caps(b,r,c,color)
                for s in seqs:caps.append({"from":(r,c),"steps":s,"capN":len(s)})
                if not seqs:
                    for dr,dc in DIRS:
                        nr,nc=r+dr,c+dc
                        while inside(nr,nc) and b[nr][nc]==0:
                            norms.append({"from":(r,c),"steps":[{"to":(nr,nc),"cap":None}],"capN":0})
                            nr+=dr;nc+=dc
    if caps:
        mx=max(m["capN"] for m in caps)
        return [m for m in caps if m["capN"]==mx]
    return norms
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Международные шашки — поддавки (2 игрока)")
        self.geometry(f"{N*CELL+420}x{N*CELL+90}")
        self.resizable(False,False)
        self.users=load_users()
        self.p1=self.p2=self.white=self.black=None
        self.frame=None
        self.protocol("WM_DELETE_WINDOW",self.on_close)
        self.show_register()
    def on_close(self):
        if messagebox.askyesno("Выход","Выйти из приложения?"):self.destroy()
    def _set_frame(self):
        if self.frame:self.frame.destroy()
        self.frame=tk.Frame(self);self.frame.pack()
    def show_register(self):
        self._set_frame()
        tk.Label(self.frame,text="Регистрация (если нужно)",font=("Arial",16,"bold")).pack(pady=8)
        tk.Label(self.frame,text="Если аккаунты уже есть — нажмите «Далее к входу».").pack()
        box=tk.Frame(self.frame);box.pack(pady=8)
        self.reg_vars=[]
        for title in ("Игрок 1","Игрок 2"):
            lf=tk.LabelFrame(box,text=title,padx=12,pady=12);lf.pack(side="left",padx=12)
            v_login,v_pw,v_msg=tk.StringVar(),tk.StringVar(),tk.StringVar(value="")
            tk.Label(lf,text="Логин").grid(row=0,column=0,sticky="w")
            tk.Entry(lf,textvariable=v_login,width=28).grid(row=1,column=0)
            tk.Label(lf,text="Пароль").grid(row=2,column=0,sticky="w",pady=(8,0))
            tk.Entry(lf,textvariable=v_pw,show="*",width=28).grid(row=3,column=0)
            def make_cmd(vl=v_login,vp=v_pw,vm=v_msg):
                def cmd():
                    ok,msg=self.register_user(vl.get().strip(),vp.get());vm.set(msg)
                    if ok:vp.set("")
                return cmd
            tk.Button(lf,text="Зарегистрировать",command=make_cmd()).grid(row=4,column=0,pady=10)
            tk.Label(lf,textvariable=v_msg,wraplength=260,justify="left").grid(row=5,column=0)
            self.reg_vars.append((v_login,v_pw,v_msg))
        btns=tk.Frame(self.frame);btns.pack(pady=10)
        tk.Button(btns,text="Далее к входу",width=22,command=self.show_login).grid(row=0,column=0,padx=6)
        tk.Button(btns,text="Выход",width=12,command=self.destroy).grid(row=0,column=1,padx=6)
    def show_login(self):
        self._set_frame()
        tk.Label(self.frame,text="Авторизация двух игроков",font=("Arial",16,"bold")).pack(pady=8)
        box=tk.Frame(self.frame);box.pack(pady=8)
        self.login_ok=[False,False];self.login_vars=[]
        self.next_btn=tk.Button(self.frame,text="Далее",width=22,state="disabled",command=self.show_firstmove)
        for i,title in enumerate(("Игрок 1","Игрок 2")):
            lf=tk.LabelFrame(box,text=title,padx=12,pady=12);lf.pack(side="left",padx=12)
            v_login,v_pw,v_msg=tk.StringVar(),tk.StringVar(),tk.StringVar(value="Не вошёл")
            tk.Label(lf,text="Логин").grid(row=0,column=0,sticky="w")
            tk.Entry(lf,textvariable=v_login,width=28).grid(row=1,column=0)
            tk.Label(lf,text="Пароль").grid(row=2,column=0,sticky="w",pady=(8,0))
            tk.Entry(lf,textvariable=v_pw,show="*",width=28).grid(row=3,column=0)
            def make_cmd(idx=i,vl=v_login,vp=v_pw,vm=v_msg):
                def cmd():
                    ok,msg=self.auth_user(vl.get().strip(),vp.get())
                    self.login_ok[idx]=ok;vm.set("Вошёл" if ok else msg);self._update_next_state()
                return cmd
            tk.Button(lf,text="Войти",command=make_cmd()).grid(row=4,column=0,pady=10)
            tk.Label(lf,textvariable=v_msg,wraplength=260,justify="left").grid(row=5,column=0)
            self.login_vars.append((v_login,v_pw,v_msg))
        self.next_btn.pack(pady=10)
        btns=tk.Frame(self.frame);btns.pack(pady=8)
        tk.Button(btns,text="Назад",width=12,command=self.show_register).grid(row=0,column=0,padx=6)
        tk.Button(btns,text="Выход",width=12,command=self.destroy).grid(row=0,column=1,padx=6)
    def _update_next_state(self):
        p1=self.login_vars[0][0].get().strip();p2=self.login_vars[1][0].get().strip()
        ok=self.login_ok[0] and self.login_ok[1] and p1 and p2 and p1!=p2
        self.next_btn.config(state=("normal" if ok else "disabled"))
    def show_firstmove(self):
        self.p1=self.login_vars[0][0].get().strip();self.p2=self.login_vars[1][0].get().strip()
        if self.p1==self.p2:return messagebox.showerror("Ошибка","Нельзя играть одним логином за двух игроков.")
        self._set_frame()
        tk.Label(self.frame,text="Кто ходит первым?",font=("Arial",16,"bold")).pack(pady=8)
        tk.Label(self.frame,text=f"Игрок 1: {self.p1}\nИгрок 2: {self.p2}",justify="left",font=("Arial",12)).pack(pady=6)
        self.first_choice=tk.StringVar(value="rand")
        f=tk.Frame(self.frame);f.pack(pady=8)
        for text,val in ((f"{self.p1} первым (белые)","p1"),(f"{self.p2} первым (белые)","p2"),("Случайно","rand")):
            tk.Radiobutton(f,text=text,variable=self.first_choice,value=val).pack(anchor="w")
        btns=tk.Frame(self.frame);btns.pack(pady=12)
        tk.Button(btns,text="Начать игру",width=22,command=self.start_game).grid(row=0,column=0,padx=6)
        tk.Button(btns,text="Сменить игроков",width=18,command=self.show_register).grid(row=0,column=1,padx=6)
        tk.Button(btns,text="Выход",width=12,command=self.destroy).grid(row=0,column=2,padx=6)
    def start_game(self):
        ch=self.first_choice.get()
        first=self.p1 if ch=="p1" else self.p2 if ch=="p2" else random.choice([self.p1,self.p2])
        self.white=first;self.black=self.p2 if first==self.p1 else self.p1
        self._set_frame()
        left=tk.Frame(self.frame);left.pack(side="left",padx=12,pady=12)
        right=tk.Frame(self.frame);right.pack(side="right",padx=12,pady=12,fill="y")
        self.canvas=tk.Canvas(left,width=N*CELL,height=N*CELL,highlightthickness=0);self.canvas.pack()
        self.canvas.bind("<Button-1>",self.on_click)
        tk.Label(right,text="Поддавки (10×10)",font=("Arial",13,"bold")).pack(anchor="w")
        tk.Label(right,text=f"Белые: {self.white}\nЧёрные: {self.black}",justify="left",font=("Arial",12)).pack(anchor="w",pady=(0,10))
        self.v_turn,self.v_force=tk.StringVar(),tk.StringVar()
        self.v_score,self.v_left,self.v_win=tk.StringVar(),tk.StringVar(),tk.StringVar(value="")
        tk.Label(right,textvariable=self.v_turn,font=("Arial",13,"bold")).pack(anchor="w")
        tk.Label(right,textvariable=self.v_force,font=("Arial",11)).pack(anchor="w")
        tk.Label(right,textvariable=self.v_score,font=("Arial",11)).pack(anchor="w",pady=(10,0))
        tk.Label(right,textvariable=self.v_left,font=("Arial",11)).pack(anchor="w")
        def btn(t,cmd,pady=3):tk.Button(right,text=t,width=22,command=cmd).pack(anchor="w",pady=pady)
        btn("Статистика",self.show_stats,(12,3));btn("Правила",self.show_rules);btn("Сыграть ещё (те же)",self.show_firstmove)
        btn("Сменить игроков",self.show_register);btn("Выход",self.destroy)
        tk.Label(right,textvariable=self.v_win,fg="#B00020",wraplength=320,justify="left",font=("Arial",13,"bold")).pack(anchor="w",pady=(14,0))
        self.images=self.make_images();self.reset_match()
    def reset_match(self):
        self.board=init_board();self.turn=1;self.white_ate=self.black_ate=0;self.game_over=False
        self.sel_pos=None;self.active=[];self.step_i=0;self.dest=set()
        self.compute_legal();self.redraw()
    def make_images(self):
        def mk(fill,king=False):
            img=tk.PhotoImage(width=CELL,height=CELL);img.put(DARK,to=(0,0,CELL,CELL))
            cx=cy=CELL//2;r=CELL//2-8;border="#333333"
            for y in range(CELL):
                for x in range(CELL):
                    dx,dy=x-cx,y-cy;d2=dx*dx+dy*dy
                    if d2<=r*r:img.put(fill,(x,y))
                    elif d2<=(r+1)*(r+1):img.put(border,(x,y))
            if king:
                rr=r//2
                for y in range(CELL):
                    for x in range(CELL):
                        dx,dy=x-cx,y-cy
                        if dx*dx+dy*dy<=rr*rr:img.put("#FFD700",(x,y))
            return img
        return {"wm":mk("#F8F8F8"),"wk":mk("#F8F8F8",True),"bm":mk("#222222"),"bk":mk("#222222",True)}
    def cur_login(self):return self.white if self.turn==1 else self.black
    def _set_info(self):
        self.v_score.set(f"Съели: белые {self.white_ate} | чёрные {self.black_ate}")
        w,b=count_pieces(self.board);self.v_left.set(f"Осталось шашек: белые {w}, чёрные {b}")
    def compute_legal(self):
        self.legal=gen_moves(self.board,self.turn);self.by_from={}
        for m in self.legal:self.by_from.setdefault(m["from"],[]).append(m)
        must=bool(self.legal) and self.legal[0]["capN"]>0
        self.v_turn.set(f"Ход: {'Белые' if self.turn==1 else 'Чёрные'} ({self.cur_login()})")
        self.v_force.set("Обязательное взятие: ДА" if must else "Обязательное взятие: НЕТ")
        self._set_info()
        if not self.legal and not self.game_over:self.finish(self.turn)
    def clear_sel(self):
        self.sel_pos=None;self.active=[];self.step_i=0;self.dest=set()
    def select_piece(self,pos):
        self.sel_pos=pos;self.active=self.by_from.get(pos,[]);self.step_i=0
        self.dest=set(m["steps"][0]["to"] for m in self.active);self.redraw()
    def apply_step(self,to_pos):
        self.active=[m for m in self.active if m["steps"][self.step_i]["to"]==to_pos]
        if not self.active:return
        step=self.active[0]["steps"][self.step_i]
        pr,pc=self.sel_pos;tr,tc=step["to"];cap=step["cap"]
        piece=self.board[pr][pc];self.board[pr][pc]=0;self.board[tr][tc]=piece
        if cap:
            cr,cc=cap
            if self.board[cr][cc]!=0:
                if self.turn==1:self.white_ate+=1
                else:self.black_ate+=1
            self.board[cr][cc]=0
        self.sel_pos=(tr,tc);self.step_i+=1
        if self.step_i>=len(self.active[0]["steps"]):
            r,c=self.sel_pos;p=self.board[r][c]
            if abs(p)==1:
                if self.turn==1 and r==0:self.board[r][c]=2
                if self.turn==-1 and r==N-1:self.board[r][c]=-2
            self.clear_sel();self.turn*=-1;self.compute_legal()
        else:self.dest=set(m["steps"][self.step_i]["to"] for m in self.active)
        self._set_info();self.redraw()
    def on_click(self,e):
        if self.game_over:return
        r,c=e.y//CELL,e.x//CELL
        if not inside(r,c):return
        if self.active and self.step_i>0:
            if (r,c) in self.dest:self.apply_step((r,c))
            return
        if self.active and (r,c) in self.dest:return self.apply_step((r,c))
        if (r,c) in self.by_from and self.board[r][c]*self.turn>0:self.select_piece((r,c))
        else:self.clear_sel();self.redraw()
    def redraw(self):
        cv=self.canvas;cv.delete("all")
        for r in range(N):
            for c in range(N):
                col=DARK if (r+c)%2 else LIGHT
                x1,y1=c*CELL,r*CELL
                cv.create_rectangle(x1,y1,x1+CELL,y1+CELL,fill=col,outline=col)
        if self.sel_pos:
            r,c=self.sel_pos;x1,y1=c*CELL,r*CELL
            cv.create_rectangle(x1+2,y1+2,x1+CELL-2,y1+CELL-2,outline=SEL_OUT,width=3)
        if self.dest:
            cap_mode=bool(self.legal) and self.legal[0]["capN"]>0
            out=CAP_OUT if cap_mode else MOVE_OUT
            for r,c in self.dest:
                x1,y1=c*CELL,r*CELL
                cv.create_rectangle(x1+6,y1+6,x1+CELL-6,y1+CELL-6,outline=out,width=3)
        for r in range(N):
            for c in range(N):
                p=self.board[r][c]
                if not p:continue
                key="wm" if p==1 else "wk" if p==2 else "bm" if p==-1 else "bk"
                cv.create_image(c*CELL+CELL//2,r*CELL+CELL//2,image=self.images[key])
    def finish(self,winner_color):
        self.game_over=True
        winner=self.white if winner_color==1 else self.black
        loser=self.black if winner_color==1 else self.white
        self.v_win.set(f"Победил: {winner}\n(поддавки: нет доступных ходов)")
        if winner in self.users:self.users[winner]["wins"]=int(self.users[winner].get("wins",0))+1
        if loser in self.users:self.users[loser]["losses"]=int(self.users[loser].get("losses",0))+1
        save_users(self.users)
    def show_rules(self):
        txt=("Краткие правила:\n• 10×10, игра на тёмных клетках.\n• Поддавки: цель — избавиться от своих шашек.\n"
             "• Если на твоём ходу нет ходов — ты выиграл.\n• Взятие обязательно; если есть варианты — бить максимум.\n"
             "• Простая ходит вперёд на 1, бьёт вперёд/назад.\n• Дамка ходит/бьёт по диагонали на любое расстояние.\n"
             "• Дамкой становится только в конце хода.\n")
        w=tk.Toplevel(self);w.title("Правила");w.resizable(False,False);w.geometry("680x340")
        t=tk.Text(w,width=90,height=12,wrap="word",font=("Arial",12));t.insert("1.0",txt);t.config(state="disabled")
        t.pack(padx=12,pady=12);tk.Button(w,text="Закрыть",width=12,command=w.destroy).pack(pady=(0,12))
    def show_stats(self):
        users=load_users();rows=[]
        for login,rec in users.items():
            wv,lv=int(rec.get("wins",0)),int(rec.get("losses",0))
            tot=wv+lv;rate=(wv/tot*100.0) if tot else 0.0
            rows.append((login,wv,lv,rate))
        rows.sort(key=lambda x:(-x[1],-x[3],x[0].lower()))
        win=tk.Toplevel(self);win.title("Статистика игроков");win.resizable(False,False);win.geometry("720x560")
        tk.Label(win,text=f"Файл: {os.path.basename(USERS_FILE)}   |   Пользователей: {len(rows)}",
                 anchor="w",font=("Arial",11)).pack(fill="x",padx=12,pady=(12,8))
        table=tk.Frame(win);table.pack(padx=12,pady=8)
        cols=("login","wins","losses","rate")
        tv=ttk.Treeview(table,columns=cols,show="headings",height=18)
        for k,t in (("login","Логин"),("wins","Победы"),("losses","Поражения"),("rate","% побед")):tv.heading(k,text=t)
        tv.column("login",width=320,anchor="w");tv.column("wins",width=90,anchor="center")
        tv.column("losses",width=110,anchor="center");tv.column("rate",width=90,anchor="center")
        sb=ttk.Scrollbar(table,orient="vertical",command=tv.yview);tv.configure(yscrollcommand=sb.set)
        tv.grid(row=0,column=0);sb.grid(row=0,column=1,sticky="ns",padx=(8,0))
        for login,wv,lv,rate in rows:tv.insert("", "end", values=(login,wv,lv,f"{rate:.0f}%"))
        btns=tk.Frame(win);btns.pack(fill="x",padx=12,pady=(8,12))
        tk.Button(btns,text="Обновить",width=12,command=lambda:(win.destroy(),self.show_stats())).pack(side="left")
        tk.Button(btns,text="Закрыть",width=12,command=win.destroy).pack(side="right")
    def register_user(self,login,pw):
        if not login or not pw:return False,"Введите логин и пароль."
        if login in self.users:return False,"Логин уже занят."
        s,h=hash_password(pw);self.users[login]={"salt":s,"hash":h,"wins":0,"losses":0};save_users(self.users)
        return True,"ОК: зарегистрирован."
    def auth_user(self,login,pw):
        rec=self.users.get(login)
        if not rec:return False,"Пользователь не найден."
        return (True,"OK") if verify_password(pw,rec["salt"],rec["hash"]) else (False,"Неверный пароль.")
if __name__=="__main__":App().mainloop()
