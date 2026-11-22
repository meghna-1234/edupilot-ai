const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let state = null, activeSubject = null, toastTimer = null;

async function api(path, method="GET", body=null) {
  const opts={method,headers:{"Content-Type":"application/json"}};
  if(body!==null) opts.body=JSON.stringify(body);
  const res=await fetch(path,opts);
  const data=await res.json().catch(()=>({error:"Unexpected server response"}));
  if(!res.ok) throw new Error(data.error||"Something went wrong");
  return data;
}
function notify(msg){const el=$("#toast");el.textContent=msg;el.classList.add("show");clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove("show"),2800)}
function safe(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function average(a){return a.length?a.reduce((x,y)=>x+y,0)/a.length:0}
function progressTasks(tasks){return tasks.length?Math.round(tasks.filter(t=>t.done).length/tasks.length*100):0}
function page(name){
  $$(".page").forEach(x=>x.classList.toggle("active",x.id==="page-"+name));
  $$(".nav-item").forEach(x=>x.classList.toggle("active",x.dataset.page===name));
  $("#crumb-name").textContent=({dashboard:"Overview",profile:"Academic profile",syllabus:"My syllabus",performance:"Performance",planner:"Study planner",tutor:"AI tutor",progress:"My progress"})[name]||name;
  $("#sidebar").classList.remove("open");
  if(name==="dashboard") renderDashboard();
  if(name==="profile") fillProfile();
  if(name==="syllabus") renderSyllabus();
  if(name==="performance") renderRecords();
  if(name==="planner") renderPlanner();
  if(name==="tutor") renderTutorOptions();
  if(name==="progress") renderProgress();
  window.scrollTo({top:0,behavior:"smooth"});
}
function bindNav(){$$("[data-page]").forEach(b=>b.addEventListener("click",()=>page(b.dataset.page)))}
async function refresh(){state=await api("/api/state");return state}
function profileLabel(){return `${state.profile.degree} · ${state.profile.branch} · Semester ${state.profile.semester}`}
function renderDashboard(){
  if(!state)return;
  const p=state.profile, subs=state.subjects, tasks=state.tasks, pct=progressTasks(tasks);
  $("#welcome-name").textContent=(p.name||"Student").split(" ")[0];
  $("#side-name").textContent=p.name||"Student";$("#side-university").textContent=p.university||"Your university";
  $("#semester-label").textContent=profileLabel();
  $("#hero-caption").textContent=subs.length?`${p.university} · ${profileLabel()}. Your plan is shaped around your current subjects and progress.`:"Add your academic details to personalize your learning space.";
  const hasScores=subs.some(s=>s.prediction.assessed);
  $("#stat-average").textContent=hasScores?`${state.average}%`:"—";
  $("#average-bar").style.width=(hasScores?state.average:0)+"%";
  $("#stat-subjects").textContent=subs.length;
  $("#stat-risk").textContent=state.needs_support;
  $("#stat-tasks").textContent=pct+"%";$("#task-bar").style.width=pct+"%";
  $("#subject-overview").innerHTML=subs.length?subs.map(s=>`<div class="subject-row"><div><b>${safe(s.code)} · ${safe(s.name)}</b><small>${safe(s.prediction.level)}</small></div><div class="bar-track"><span style="width:${s.prediction.assessed?s.prediction.score:0}%"></span></div><strong>${s.prediction.assessed?s.prediction.score+"%":"—"}</strong></div>`).join(""):`<div class="empty">Set up your profile to load your subjects.</div>`;
  const upcoming=tasks.filter(t=>!t.done).slice(0,3);
  $("#next-steps").innerHTML=upcoming.length?upcoming.map(t=>`<div class="next-item"><span class="next-dot">↗</span><div><b>${safe(t.title)}</b><small>${safe(t.due_day)} · ${t.minutes} min</small></div></div>`).join(""):`<div class="empty">No tasks yet. Generate your first plan.</div>`;
  const allM=subs.flatMap(s=>s.mastery.map(m=>m.score));
  $("#learning-snapshot").innerHTML=allM.length?`<div class="snapshot-grid"><div class="snapshot-cell"><b>${Math.round(average(allM))}%</b><small>Average topic mastery</small></div><div class="snapshot-cell"><b>${allM.filter(x=>x>=70).length}</b><small>Topics at target</small></div><div class="snapshot-cell"><b>${allM.length}</b><small>Topics assessed</small></div></div>`:`<div class="empty">Complete a lesson assessment to start tracking topic mastery.</div>`;
  $("#today-label").textContent=new Date().toLocaleDateString(undefined,{weekday:"short",month:"short",day:"numeric"});
}
function fillProfile(){
  const p=state.profile;
  for(const [id,key] of [["profile-name","name"],["profile-university","university"],["profile-degree","degree"],["profile-branch","branch"],["profile-year","year"],["profile-semester","semester"],["profile-regulation","regulation"],["profile-minutes","daily_minutes"]]){
    const el=$("#"+id);if(el)el.value=p[key]??el.value;
  }
}
$("#profile-form").addEventListener("submit",async e=>{
  e.preventDefault();const f=new FormData(e.currentTarget),body={};
  for(const k of ["name","university","degree","branch","regulation"])body[k]=f.get(k);
  for(const k of ["year","semester","daily_minutes"])body[k]=Number(f.get(k));
  try{
    const r=await api("/api/profile","POST",body);await refresh();
    $("#profile-message").textContent=r.syllabus_found?`Profile saved. Loaded ${r.subjects_loaded} subjects from the local syllabus catalogue.`:"Profile saved. No exact catalogue match was found; upload a syllabus JSON or add a supported curriculum.";
    notify("Academic profile saved");renderDashboard();
  }catch(err){$("#profile-message").textContent=err.message}
});
function renderSyllabus(){
  if(!state)return;
  $("#syllabus-university").textContent=state.profile.university||"University not set";
  $("#syllabus-meta").textContent=profileLabel()+" · Regulation "+state.profile.regulation;
  $("#syllabus-count").textContent=`${state.subjects.length} subjects in your curriculum`;
  $("#syllabus-list").innerHTML=state.subjects.length?state.subjects.map((s,si)=>`
    <article class="subject-card"><div class="subject-card-head"><div><span class="subject-code">${safe(s.code)}</span><h3>${safe(s.name)}</h3><p>${s.units.length} units · ${s.units.reduce((n,u)=>n+(u.topics||[]).length,0)} topics</p></div><span class="level">${s.prediction.score}%</span></div>
    <div class="unit-list">${s.units.map((u,i)=>`<div class="unit-item"><button class="unit-toggle" data-unit-toggle="${si}-${i}"><span>Unit ${i+1} · ${safe(u.title)}</span><span>＋</span></button><div class="unit-topics">${(u.topics||[]).map(t=>`<span>• ${safe(t)}</span>`).join("")}</div></div>`).join("")}</div></article>`).join(""):`<div class="empty panel">No syllabus loaded. Update your academic profile or upload a syllabus JSON.</div>`;
  $$("[data-unit-toggle]").forEach(b=>b.onclick=()=>b.parentElement.classList.toggle("open"));
}
$("#syllabus-file").addEventListener("change",async e=>{
  const file=e.target.files[0];if(!file)return;
  try{const data=JSON.parse(await file.text());const subjects=Array.isArray(data)?data:data.subjects;const r=await api("/api/syllabus/upload","POST",{subjects});await refresh();renderSyllabus();notify(`Loaded ${r.subjects_loaded} syllabus subjects`)}
  catch(err){notify("Syllabus upload: "+err.message)}e.target.value="";
});
function renderRecords(){
  $("#records-inputs").innerHTML=state.subjects.length?`<div class="records-table-wrap"><table class="records-table"><thead><tr><th>SUBJECT</th><th>ATTENDANCE %</th><th>MARKS %</th><th>ASSIGNMENTS %</th><th>INTERNAL %</th></tr></thead><tbody>${state.subjects.map(s=>`<tr data-record="${safe(s.code)}"><td><b>${safe(s.code)}</b><br><span class="muted">${safe(s.name)}</span></td>${["attendance","marks","assignment","internal"].map(k=>`<td><input type="number" min="0" max="100" step="0.1" data-field="${k}" value="${s.record[k]??""}"></td>`).join("")}</tr>`).join("")}</tbody></table></div>`:`<div class="empty">Load your syllabus first to enter subject records.</div>`;
  renderResults();
}
function renderResults(){
  $("#performance-results").innerHTML=state.subjects.length?state.subjects.map(s=>`<article class="result-card"><div class="result-head"><b>${safe(s.code)} · ${safe(s.name)}</b><span class="score-chip">${s.prediction.assessed?s.prediction.score+"%":"—"}</span></div><p><span class="level ${s.prediction.needs_support?"risk":s.prediction.level==="Good"||s.prediction.level==="Excellent"?"good":""}">${safe(s.prediction.level)}</span></p><div class="bar-track"><span style="width:${s.prediction.assessed?s.prediction.score:0}%"></span></div><p>${!s.prediction.assessed?"Enter academic records to generate an estimate.":s.prediction.weak_areas.length?"Areas to review: "+s.prediction.weak_areas.join(", "):"No factor fell below the configured thresholds."}</p></article>`).join(""):`<div class="empty panel">No performance data yet.</div>`;
}
$("#records-form").addEventListener("submit",async e=>{
  e.preventDefault();const subjects=$$("#records-inputs tr[data-record]").map(tr=>({code:tr.dataset.record,...Object.fromEntries([...tr.querySelectorAll("input")].map(i=>[i.dataset.field,Number(i.value)]))}));
  try{await api("/api/records","POST",{subjects});await refresh();renderRecords();renderDashboard();notify("Performance records analyzed")}
  catch(err){notify(err.message)}
});
function renderPlanner(){
  const tasks=state.tasks||[],done=tasks.filter(t=>t.done).length;
  $("#plan-summary").innerHTML=`<div class="plan-stat"><b>${tasks.length}</b><small>Planned learning sessions</small></div><div class="plan-stat"><b>${done}</b><small>Sessions completed</small></div><div class="plan-stat"><b>${progressTasks(tasks)}%</b><small>Plan progress</small></div>`;
  $("#task-list").innerHTML=tasks.length?tasks.map(t=>`<div class="task-card ${t.done?"done":""}"><input class="task-check" type="checkbox" data-task="${t.id}" ${t.done?"checked":""}><div class="task-info"><b>${safe(t.title)}</b><small>${safe(t.code)} · ${t.minutes} minutes · Unit ${t.unit_index+1}</small></div><span class="task-date">${safe(t.due_day)}</span><button class="text-btn" data-open-tutor="${safe(t.code)}" data-unit="${t.unit_index}">Learn →</button></div>`).join(""):`<div class="empty panel">Generate your personalized study plan to see your tasks.</div>`;
  $$("[data-task]").forEach(cb=>cb.onchange=async()=>{await api("/api/tasks/toggle","POST",{id:cb.dataset.task,done:cb.checked});await refresh();renderPlanner();renderDashboard()});
  $$("[data-open-tutor]").forEach(b=>b.onclick=()=>{page("tutor");$("#tutor-subject").value=b.dataset.openTutor;renderTutorUnits(Number(b.dataset.unit))});
}
$("#generate-plan").addEventListener("click",async()=>{try{await api("/api/plan/generate","POST",{});await refresh();renderPlanner();renderDashboard();notify("Your personalized plan is ready")}catch(e){notify(e.message)}});
function renderTutorOptions(){
  const sel=$("#tutor-subject"),cur=sel.value;
  sel.innerHTML=state.subjects.map(s=>`<option value="${safe(s.code)}">${safe(s.code)} · ${safe(s.name)}</option>`).join("");
  if(cur&&state.subjects.some(s=>s.code===cur))sel.value=cur;
  renderTutorUnits();
}
function renderTutorUnits(preferred=null){
  const sub=state.subjects.find(s=>s.code===$("#tutor-subject").value);
  $("#tutor-unit").innerHTML=sub?sub.units.map((u,i)=>`<option value="${i}">Unit ${i+1} · ${safe(u.title)}</option>`).join(""):"";
  if(preferred!==null&&sub&&sub.units[preferred])$("#tutor-unit").value=preferred;
}
$("#tutor-subject").addEventListener("change",()=>renderTutorUnits());
function addMessage(text,who,html=false){
  const div=document.createElement("div");div.className="chat-bubble "+who;
  if(html)div.innerHTML=text;else div.textContent=text;
  $("#chat-messages").appendChild(div);$("#chat-messages").scrollTop=$("#chat-messages").scrollHeight;
}
function mdLite(text){
  return safe(text).replace(/^## (.*)$/gm,"<b>$1</b>").replace(/\*\*(.*?)\*\*/g,"<b>$1</b>").replace(/\n/g,"<br>");
}
async function askTutor(prompt){
  const code=$("#tutor-subject").value,unit_index=Number($("#tutor-unit").value);
  if(!code){notify("Load a syllabus first");return}
  addMessage(prompt,"user");
  $("#tutor-status").textContent="Thinking about your question…";
  try{
    const r=await api("/api/tutor","POST",{code,unit_index,prompt});
    addMessage(mdLite(r.answer),"tutor",true);
    $("#tutor-status").textContent=r.mode==="llm"?"AI tutor · Personalized response":"Syllabus-based tutor · Demo mode";
    if(/quiz|test me|question|practice/i.test(prompt)){
      const box=document.createElement("div");box.className="chat-bubble tutor";
      box.innerHTML=`<b>How did that feel?</b><p>After attempting the questions, rate your understanding so I can update your learning plan.</p><div class="mastery-buttons"><button data-mastery="30">Still unsure</button><button data-mastery="55">Getting there</button><button data-mastery="75">Understood</button><button data-mastery="90">Confident</button></div>`;
      $("#chat-messages").appendChild(box);
      box.querySelectorAll("[data-mastery]").forEach(b=>b.onclick=async()=>{await api("/api/assessment/submit","POST",{code,unit_index,score:Number(b.dataset.mastery)});await refresh();renderDashboard();renderProgress();box.innerHTML=`<b>Learning profile updated: ${b.dataset.mastery}%</b><p>I'll use this result to help shape your next study steps.</p>`;notify("Topic mastery updated")});
    }
  }catch(e){addMessage("I couldn't complete that request: "+e.message,"tutor")}
  $("#tutor-status").textContent="Syllabus-grounded tutor · Ready";
}
$("#chat-form").addEventListener("submit",e=>{e.preventDefault();const input=$("#chat-input"),q=input.value.trim();if(!q)return;input.value="";askTutor(q)});
$$("[data-prompt]").forEach(b=>b.addEventListener("click",()=>askTutor(b.dataset.prompt)));
function renderProgress(){
  const all=state.subjects.flatMap(s=>s.mastery),assessed=all.filter(m=>m.confidence>0),pct=assessed.length?Math.round(average(assessed.map(m=>m.score))):0;
  $("#progress-number").textContent=pct+"%";
  $("#progress-circle").style.background=`conic-gradient(#fff ${pct*3.6}deg,#ffffff30 0deg)`;
  $("#progress-headline").textContent=assessed.length?(pct>=70?"You're building strong understanding.":pct>=45?"You're making steady progress.":"Every assessment is a useful starting point."):"Every topic is a fresh start.";
  $("#progress-copy").textContent=assessed.length?`${assessed.length} topic assessments are contributing to your current mastery estimate.`:"Complete a lesson assessment to build your learning profile.";
  $("#mastery-grid").innerHTML=state.subjects.length?state.subjects.map(s=>`<article class="mastery-card"><h3>${safe(s.code)} · ${safe(s.name)}</h3>${s.units.map((u,i)=>{const m=s.mastery.find(x=>x.unit_index===i);const v=m?m.score:0;return `<div class="mastery-row"><span>Unit ${i+1} · ${safe(u.title)}</span><b>${m&&m.confidence>0?v+"%":"Not assessed"}</b></div><div class="bar-track"><span style="width:${m&&m.confidence>0?v:0}%"></span></div>`}).join("")}</article>`).join(""):`<div class="empty panel">No syllabus loaded.</div>`;
}
async function init(){
  bindNav();$("#menu-toggle").onclick=()=>$("#sidebar").classList.toggle("open");
  try{await refresh();renderDashboard();fillProfile();}catch(e){notify("Could not connect to the local server: "+e.message)}
}
init();
