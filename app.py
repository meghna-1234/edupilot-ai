"""
EduPilot AI — self-contained MVP server.
Uses Python standard library + SQLite. Optional LLM integration via environment variables.
Run: python app.py
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import json, os, sqlite3, csv, io, uuid, urllib.request, urllib.error
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "edupilot.db")
CATALOG_PATH = os.path.join(BASE, "data", "syllabus_catalog.json")
HOST, PORT = "127.0.0.1", int(os.environ.get("PORT", "8000"))

DEFAULT_CATALOG = {
  "universities": [{
    "name": "Demo Technical University",
    "aliases": ["demo university", "sample technical university"],
    "regulations": ["2024"],
    "degrees": ["B.Tech"],
    "branches": [{
      "name": "Computer Science and Engineering", "code": "CSE",
      "years": [1,2,3,4],
      "semesters": {
        "3": [
          {"code":"DSA","name":"Data Structures and Algorithms","units":[
            {"title":"Algorithm Analysis","topics":["Time and space complexity","Asymptotic notation","Recurrence relations"],"lesson":"Algorithm analysis estimates how an algorithm's resource use grows with input size. Big-O describes an upper growth bound, while Omega describes a lower bound and Theta describes a tight bound. Compare algorithms by counting dominant operations rather than relying only on machine run time.","questions":["What does Big-O notation describe?","Compare O(n) and O(n²) growth.","Why do we ignore constant factors in asymptotic analysis?"]},
            {"title":"Linear Data Structures","topics":["Arrays","Linked lists","Stacks","Queues"],"lesson":"Linear data structures arrange elements in a sequence. Arrays provide indexed access, linked lists connect nodes through references, stacks follow last-in-first-out order, and queues follow first-in-first-out order.","questions":["Explain the LIFO principle.","When might a linked list be preferred over an array?","Give one real-world queue example."]},
            {"title":"Trees and Graphs","topics":["Binary trees","Tree traversals","Binary search trees","Graph representations"],"lesson":"Trees represent hierarchical relationships. A binary tree has at most two children per node. Common traversals include preorder, inorder and postorder. Graphs model general relationships using vertices and edges.","questions":["What is the difference between a tree and a graph?","Name three depth-first tree traversals.","What is an adjacency list?"]}
          ]},
          {"code":"DBMS","name":"Database Management Systems","units":[
            {"title":"Database Fundamentals","topics":["Database concepts","DBMS architecture","Data independence"],"lesson":"A database is an organized collection of related data. A DBMS provides controlled ways to define, store, query and protect that data. Data independence separates applications from details of physical storage or logical schema changes.","questions":["What is a DBMS?","Differentiate logical and physical data independence.","State two advantages of a DBMS."]},
            {"title":"Relational Model and SQL","topics":["Relations and tuples","Keys","SQL DDL and DML","Joins"],"lesson":"The relational model stores data in relations (tables). Rows are tuples and columns are attributes. Keys identify rows and connect tables. SQL defines schemas, inserts and updates data, and retrieves information using queries and joins.","questions":["What is a primary key?","Differentiate DDL and DML.","Why are joins used?"]},
            {"title":"Normalization and Transactions","topics":["Functional dependencies","1NF, 2NF and 3NF","ACID properties","Concurrency control"],"lesson":"Normalization organizes relations to reduce unwanted redundancy and update anomalies. Transactions are logical units of work. ACID means atomicity, consistency, isolation and durability.","questions":["What is a functional dependency?","What problem does normalization address?","Explain the ACID properties."]}
          ]},
          {"code":"OS","name":"Operating Systems","units":[
            {"title":"OS Fundamentals and Processes","topics":["OS functions","Process states","Process control block","Threads"],"lesson":"An operating system manages hardware resources and provides services to programs. A process is a program in execution. Its state may be new, ready, running, waiting or terminated. A process control block stores information needed to manage it.","questions":["List four major functions of an operating system.","What is a process control block?","Differentiate a process and a thread."]},
            {"title":"CPU Scheduling and Synchronization","topics":["FCFS","SJF","Round Robin","Critical sections","Semaphores"],"lesson":"CPU scheduling selects a ready process for execution. FCFS uses arrival order, SJF selects the shortest estimated job, and Round Robin gives each process a time quantum. Synchronization coordinates shared-resource access to avoid race conditions.","questions":["How does Round Robin scheduling work?","What is a critical section?","Why are semaphores used?"]},
            {"title":"Deadlocks and Memory Management","topics":["Deadlock conditions","Deadlock handling","Paging","Virtual memory"],"lesson":"A deadlock is a situation where processes wait indefinitely for resources held by one another. The four necessary conditions are mutual exclusion, hold and wait, no preemption and circular wait. Paging divides memory into fixed-size pages and frames; virtual memory lets processes use an address space larger than physical RAM.","questions":["Name the four necessary deadlock conditions.","What is paging?","What is the purpose of virtual memory?"]}
          ]}
        ]
      }
    }]
  }]
}

def db():
    c=sqlite3.connect(DB_PATH)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    os.makedirs(os.path.dirname(CATALOG_PATH), exist_ok=True)
    if not os.path.exists(CATALOG_PATH):
        with open(CATALOG_PATH,"w",encoding="utf-8") as f: json.dump(DEFAULT_CATALOG,f,indent=2)
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS profile(id INTEGER PRIMARY KEY CHECK(id=1), name TEXT DEFAULT 'Student', university TEXT DEFAULT 'Demo Technical University', degree TEXT DEFAULT 'B.Tech', branch TEXT DEFAULT 'CSE', year INTEGER DEFAULT 2, semester INTEGER DEFAULT 3, regulation TEXT DEFAULT '2024', daily_minutes INTEGER DEFAULT 60);
    CREATE TABLE IF NOT EXISTS subjects(code TEXT PRIMARY KEY, name TEXT NOT NULL, syllabus_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS records(code TEXT PRIMARY KEY, attendance REAL, marks REAL, assignment REAL, internal REAL, FOREIGN KEY(code) REFERENCES subjects(code) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS mastery(code TEXT, unit_index INTEGER, score REAL DEFAULT 0, confidence REAL DEFAULT 0, PRIMARY KEY(code,unit_index), FOREIGN KEY(code) REFERENCES subjects(code) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, code TEXT, unit_index INTEGER, title TEXT, due_day TEXT, done INTEGER DEFAULT 0, minutes INTEGER DEFAULT 30);
    CREATE TABLE IF NOT EXISTS tutor_log(id INTEGER PRIMARY KEY AUTOINCREMENT, prompt TEXT, response TEXT, created_at TEXT);
    """)
    c.execute("INSERT OR IGNORE INTO profile(id, university) VALUES(1, 'Demo Technical University')")
    c.commit()
    has_subjects = c.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    c.close()
    if not has_subjects:
        profile = {"university":"Demo Technical University","degree":"B.Tech","branch":"CSE","semester":3}
        _, starter = get_syllabus_for_profile(profile)
        if starter: install_syllabus(starter)

def read_catalog():
    try:
        with open(CATALOG_PATH,encoding="utf-8") as f: return json.load(f)
    except Exception: return DEFAULT_CATALOG

def catalog_matches(q):
    q=(q or "").strip().lower()
    cat=read_catalog()
    out=[]
    for uni in cat.get("universities",[]):
        names=[uni.get("name","")]+uni.get("aliases",[])
        if not q or any(q in n.lower() or n.lower() in q for n in names):
            out.append(uni)
    return out

def get_syllabus_for_profile(profile):
    matches=catalog_matches(profile.get("university",""))
    for uni in matches:
        for deg in uni.get("degrees",[]):
            if deg.lower()==profile.get("degree","").lower():
                for branch in uni.get("branches",[]):
                    if (branch.get("code","").lower()==profile.get("branch","").lower()
                        or branch.get("name","").lower()==profile.get("branch","").lower()):
                        return uni, branch.get("semesters",{}).get(str(profile.get("semester")),[])
    return None, []

def score_record(r):
    weights={"marks":.35,"internal":.25,"assignment":.20,"attendance":.20}
    if not any(r.get(k) is not None for k in weights):
        return {"score":0,"level":"Not assessed","weak_areas":[],"needs_support":False,"assessed":False}
    vals={k:float(r.get(k) or 0) for k in weights}
    score=round(sum(vals[k]*v for k,v in weights.items()),1)
    weak=[]
    limits={"attendance":75,"marks":40,"internal":40,"assignment":50}
    for k,lim in limits.items():
        if vals[k]<lim: weak.append(k)
    level="Excellent" if score>=80 and not weak else "Good" if score>=65 and not weak else "Average" if score>=50 and len(weak)<=1 else "Needs Support"
    return {"score":score,"level":level,"weak_areas":weak,"needs_support":level=="Needs Support","assessed":True}

def current_state():
    c=db()
    profile=dict(c.execute("SELECT * FROM profile WHERE id=1").fetchone())
    subjects=[]
    for row in c.execute("SELECT * FROM subjects ORDER BY code"):
        sub=dict(row); sub["units"]=json.loads(sub.pop("syllabus_json"))
        rec=c.execute("SELECT * FROM records WHERE code=?",(sub["code"],)).fetchone()
        sub["record"]=dict(rec) if rec else {"attendance":0,"marks":0,"assignment":0,"internal":0}
        sub["prediction"]=score_record(sub["record"])
        m=c.execute("SELECT unit_index,score,confidence FROM mastery WHERE code=? ORDER BY unit_index",(sub["code"],)).fetchall()
        sub["mastery"]=[dict(x) for x in m]
        subjects.append(sub)
    tasks=[dict(x) for x in c.execute("SELECT * FROM tasks ORDER BY due_day,id")]
    c.close()
    assessed=[s["prediction"]["score"] for s in subjects if s["prediction"].get("assessed")]
    avg=round(sum(assessed)/len(assessed),1) if assessed else 0
    return {"profile":profile,"subjects":subjects,"tasks":tasks,"average":avg,
            "needs_support":sum(s["prediction"]["needs_support"] for s in subjects),
            "catalog_universities":[u["name"] for u in read_catalog().get("universities",[])]}

def install_syllabus(subjects):
    c=db()
    c.execute("DELETE FROM tasks"); c.execute("DELETE FROM mastery"); c.execute("DELETE FROM records"); c.execute("DELETE FROM subjects")
    for sub in subjects:
        code=sub.get("code") or "SUB"+uuid.uuid4().hex[:4].upper()
        units=sub.get("units",[])
        c.execute("INSERT INTO subjects(code,name,syllabus_json) VALUES(?,?,?)",(code,sub.get("name",code),json.dumps(units)))
        c.execute("INSERT INTO records(code) VALUES(?)",(code,))
        for i,_ in enumerate(units): c.execute("INSERT INTO mastery(code,unit_index,score,confidence) VALUES(?,?,?,?)",(code,i,0,0))
    c.commit(); c.close()

def generate_plan():
    state=current_state(); c=db()
    c.execute("DELETE FROM tasks")
    tasks=[]
    start=date.today()
    day_offset=0
    for sub in sorted(state["subjects"],key=lambda x:x["prediction"]["score"]):
        weak_units=[]
        for i,u in enumerate(sub["units"]):
            m=next((x for x in sub["mastery"] if x["unit_index"]==i),None)
            score=(m["score"] if m else 0)
            if score<70: weak_units.append((i,u,score))
        if not weak_units and sub["units"]: weak_units=[(0,sub["units"][0],0)]
        for i,u,score in weak_units:
            title=f'{sub["code"]}: {u.get("title","Unit")} — learn & practice'
            due=(start+timedelta(days=day_offset)).isoformat()
            tid=uuid.uuid4().hex[:10]
            c.execute("INSERT INTO tasks(id,code,unit_index,title,due_day,done,minutes) VALUES(?,?,?,?,?,0,?)",(tid,sub["code"],i,title,due,45))
            tasks.append({"id":tid,"code":sub["code"],"unit_index":i,"title":title,"due_day":due,"done":0,"minutes":45})
            day_offset+=1
    c.commit(); c.close()
    return tasks

def update_mastery(code, unit, score, confidence=None):
    c=db()
    c.execute("INSERT INTO mastery(code,unit_index,score,confidence) VALUES(?,?,?,?) ON CONFLICT(code,unit_index) DO UPDATE SET score=excluded.score,confidence=excluded.confidence",(code,int(unit),float(score),float(confidence if confidence is not None else score)))
    c.commit(); c.close()

def fallback_tutor(prompt, subject, unit):
    title=unit.get("title","the selected topic")
    topics=unit.get("topics",[])
    lesson=unit.get("lesson","")
    questions=unit.get("questions",[])
    p=prompt.lower()
    if any(x in p for x in ["quiz","test me","question","practice"]):
        qs="\n".join(f"{i+1}. {q}" for i,q in enumerate(questions[:3]))
        return f"Let's check your understanding of **{title}**.\n\n{qs}\n\nReply with your answers (1, 2, 3). I'll help you review them."
    if any(x in p for x in ["simple","simpler","beginner","explain"]):
        return f"## {title}\n\n{lesson}\n\n### Topics in this unit\n" + "\n".join(f"- {t}" for t in topics) + "\n\n**Quick check:** In your own words, explain one idea from this lesson. I can then adapt the next explanation."
    return f"## Let's work on {title}\n\n{lesson}\n\n### Topics to cover\n" + "\n".join(f"- {t}" for t in topics) + "\n\n### Try this\n{(questions[0] if questions else 'Summarize the main idea in your own words.')}\n\nThis built-in tutor uses the saved syllabus content. Add an LLM API key to enable generated, more conversational teaching."

def llm_tutor(prompt, subject, unit, profile):
    key=os.environ.get("OPENAI_API_KEY")
    if not key: return fallback_tutor(prompt,subject,unit), "syllabus-fallback"
    base=os.environ.get("OPENAI_BASE_URL","https://api.openai.com/v1").rstrip("/")
    model=os.environ.get("OPENAI_MODEL","gpt-4o-mini")
    system=("You are EduPilot, a supportive academic tutor. Teach only in context of the supplied syllabus. "
            "Adapt to the learner's level, explain step by step, use examples, and do not claim unsupported syllabus facts. "
            "When asked to quiz, ask questions but do not reveal answers until the learner attempts them.")
    context=json.dumps({"student_profile":profile,"subject":subject.get("name"),"unit":unit})
    body={"model":model,"messages":[{"role":"system","content":system+"\nContext: "+context},{"role":"user","content":prompt}],"temperature":0.5}
    req=urllib.request.Request(base+"/chat/completions",data=json.dumps(body).encode(),headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=20) as r: data=json.loads(r.read().decode())
        return data["choices"][0]["message"]["content"], "llm"
    except Exception:
        return fallback_tutor(prompt,subject,unit), "syllabus-fallback"

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): print("%s - %s"%(self.address_string(),fmt%args))
    def send_json(self, status, obj):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store")
        self.end_headers(); self.wfile.write(raw)
    def body(self):
        n=int(self.headers.get("Content-Length","0"))
        if n>5_000_000: raise ValueError("Request too large")
        raw=self.rfile.read(n)
        return json.loads(raw.decode("utf-8")) if raw else {}
    def static(self,path):
        files={"/":("index.html","text/html"),"/index.html":("index.html","text/html"),
               "/style.css":("static/style.css","text/css"),"/script.js":("static/script.js","application/javascript"),
               "/data/syllabus_catalog.json":("data/syllabus_catalog.json","application/json")}
        if path not in files: return False
        name,typ=files[path]; raw=open(os.path.join(BASE,name),"rb").read()
        self.send_response(200); self.send_header("Content-Type",typ+"; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw); return True
    def do_GET(self):
        path=urlparse(self.path).path
        if self.static(path): return
        if path=="/api/state": return self.send_json(200,current_state())
        if path=="/api/syllabus/catalog": return self.send_json(200,read_catalog())
        if path=="/api/health": return self.send_json(200,{"ok":True,"app":"EduPilot AI"})
        return self.send_json(404,{"error":"Not found"})
    def do_POST(self):
        path=urlparse(self.path).path
        try:
            data=self.body()
            if path=="/api/profile":
                c=db()
                fields=["name","university","degree","branch","year","semester","regulation","daily_minutes"]
                vals=[data.get(k) for k in fields]
                c.execute("UPDATE profile SET "+",".join(k+"=?" for k in fields)+" WHERE id=1",vals)
                c.commit(); c.close()
                uni,subs=get_syllabus_for_profile(data)
                install_syllabus(subs)
                return self.send_json(200,{"ok":True,"syllabus_found":bool(subs),"subjects_loaded":len(subs)})
            if path=="/api/syllabus/load":
                subjects=data.get("subjects",[])
                if not subjects: return self.send_json(400,{"error":"No subjects supplied"})
                install_syllabus(subjects); return self.send_json(200,{"ok":True,"subjects_loaded":len(subjects)})
            if path=="/api/records":
                c=db()
                for item in data.get("subjects",[]):
                    vals=[float(item.get(k,0)) for k in ["attendance","marks","assignment","internal"]]
                    if any(v<0 or v>100 for v in vals): raise ValueError("All academic values must be between 0 and 100")
                    c.execute("INSERT INTO records(code,attendance,marks,assignment,internal) VALUES(?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET attendance=excluded.attendance,marks=excluded.marks,assignment=excluded.assignment,internal=excluded.internal",(item["code"],*vals))
                c.commit(); c.close(); return self.send_json(200,{"ok":True})
            if path=="/api/plan/generate":
                tasks=generate_plan(); return self.send_json(200,{"tasks":tasks})
            if path=="/api/tasks/toggle":
                c=db(); c.execute("UPDATE tasks SET done=? WHERE id=?",(1 if data.get("done") else 0,data.get("id"))); c.commit(); c.close()
                return self.send_json(200,{"ok":True})
            if path=="/api/tutor":
                state=current_state(); sub=next((s for s in state["subjects"] if s["code"]==data.get("code")),None)
                if not sub: return self.send_json(404,{"error":"Choose a subject first"})
                idx=int(data.get("unit_index",0))
                if idx<0 or idx>=len(sub["units"]): return self.send_json(400,{"error":"Invalid unit"})
                unit=sub["units"][idx]
                answer,mode=llm_tutor(data.get("prompt","Explain this topic simply."),sub,unit,state["profile"])
                c=db(); c.execute("INSERT INTO tutor_log(prompt,response,created_at) VALUES(?,?,?)",(data.get("prompt",""),answer,datetime.now().isoformat(timespec="seconds"))); c.commit(); c.close()
                return self.send_json(200,{"answer":answer,"mode":mode,"unit_title":unit.get("title")})
            if path=="/api/assessment/submit":
                code=data.get("code"); idx=int(data.get("unit_index",0)); score=float(data.get("score",0))
                if not 0<=score<=100: raise ValueError("Assessment score must be between 0 and 100")
                update_mastery(code,idx,score,score)
                return self.send_json(200,{"ok":True,"mastery":score})
            if path=="/api/syllabus/upload":
                # Accept structured JSON curriculum in MVP; PDF extraction is an optional extension.
                subjects=data.get("subjects",[])
                if not subjects: return self.send_json(400,{"error":"Upload a syllabus JSON with a subjects array. PDF extraction can be enabled with the optional parser."})
                install_syllabus(subjects); return self.send_json(200,{"ok":True,"subjects_loaded":len(subjects)})
            return self.send_json(404,{"error":"Not found"})
        except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e:
            return self.send_json(400,{"error":str(e)})
        except Exception as e:
            return self.send_json(500,{"error":"Server error: "+str(e)})

if __name__=="__main__":
    init_db()
    print(f"\nEduPilot AI running at http://localhost:{PORT}\nPress Ctrl+C to stop.\n")
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
