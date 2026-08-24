/* DataForge Mobile: offline visual SQLite assembly studio. */
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const state={db:null,plan:{name:'Untitled Work Table',main:'',joins:[],outputs:[],filters:[],groups:[],sorts:[],distinct:false,limit:1000},pick:null,result:{columns:[],rows:[]}};
const q=n=>'"'+String(n).replaceAll('"','""')+'"', ref=x=>x==='*'?'*':x.split('.').map(q).join('.');
const clean=s=>(String(s).trim().replace(/\W+/g,'_').replace(/^_+|_+$/g,'')||'field').replace(/^(\d)/,'_$1');

async function start(){
 const SQLite=window.SQL; let bytes=await idbGet('database');
 if(!SQLite||!SQLite.Database)throw Error('SQLite engine did not initialize');
 try{state.db=bytes?new SQLite.Database(new Uint8Array(bytes)):new SQLite.Database()}catch(e){state.db=new SQLite.Database()}
 meta();let seeded=false;if(!tables().length){seedSampleData();seeded=true;await persist()}else loadStarterPlan();bind();render();status(seeded?'Demo ready — inspect the joins or press Run':'SQLite ready — sample project available');
}
function meta(){state.db.run('CREATE TABLE IF NOT EXISTS _dataforge_queries(name TEXT PRIMARY KEY, plan_json TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)')}
function seedSampleData(){
 state.db.run(`
  CREATE TABLE Customers(id INTEGER PRIMARY KEY,name TEXT,city TEXT,segment TEXT);
  INSERT INTO Customers VALUES
   (1,'Northwind Works','Riverton','Commercial'),(2,'Lakeview Electric','Fairview','Home Services'),
   (3,'Maple Street Cafe','Riverton','Hospitality'),(4,'Summit Plumbing','Franklin','Home Services'),
   (5,'Blue Heron Design','Greenville','Professional'),(6,'Red Barn Market','Oakridge','Retail'),
   (7,'Evergreen Dental','Riverton','Healthcare'),(8,'Ironworks Garage','Georgetown','Automotive');
  CREATE TABLE Products(id INTEGER PRIMARY KEY,name TEXT,category TEXT,price REAL);
  INSERT INTO Products VALUES
   (1,'Website Rebuild','Web',2400),(2,'SEO Launch','Marketing',1200),(3,'Lead Dashboard','Software',3200),
   (4,'Hosting Annual','Infrastructure',360),(5,'Automation Setup','Automation',1800),(6,'Data Cleanup','Data',750),
   (7,'Mobile App','Software',4500),(8,'Analytics Package','Marketing',950);
  CREATE TABLE Orders(id INTEGER PRIMARY KEY,customer_id INTEGER,product_id INTEGER,order_date TEXT,quantity INTEGER,total REAL,status TEXT);
  INSERT INTO Orders VALUES
   (101,1,3,'2026-06-03',1,3200,'Paid'),(102,1,2,'2026-06-04',2,2400,'Paid'),
   (103,2,1,'2026-06-08',1,2400,'Paid'),(104,2,4,'2026-06-08',1,360,'Paid'),
   (105,3,2,'2026-06-12',1,1200,'Pending'),(106,3,8,'2026-06-14',1,950,'Paid'),
   (107,4,5,'2026-06-19',1,1800,'Paid'),(108,4,6,'2026-06-20',2,1500,'Paid'),
   (109,5,7,'2026-06-23',1,4500,'Paid'),(110,5,8,'2026-06-24',1,950,'Paid'),
   (111,6,1,'2026-07-02',1,2400,'Pending'),(112,7,3,'2026-07-05',1,3200,'Paid'),
   (113,7,4,'2026-07-05',1,360,'Paid'),(114,8,5,'2026-07-09',1,1800,'Paid'),
   (115,8,6,'2026-07-10',1,750,'Paid');
 `);
 state.plan={name:'Sample Revenue by Customer',main:'Customers',joins:[
  {table:'Orders',left:'Customers.id',right:'Orders.customer_id',kind:'LEFT'},
  {table:'Products',left:'Orders.product_id',right:'Products.id',kind:'LEFT'}
 ],outputs:[
  {ref:'Customers.name',agg:'',alias:'Customer'},{ref:'Orders.total',agg:'SUM',alias:'Revenue'},
  {ref:'Customers.city',agg:'',alias:'City'},{ref:'Products.category',agg:'',alias:'Category'},
  {ref:'Orders.id',agg:'COUNT',alias:'Orders'}
 ],filters:[],groups:['Customers.name','Customers.city','Products.category'],sorts:[{ref:'Revenue',dir:'DESC'}],distinct:false,limit:1000};
 state.db.run('INSERT OR REPLACE INTO _dataforge_queries(name,plan_json,updated_at) VALUES(?,?,CURRENT_TIMESTAMP)',[state.plan.name,JSON.stringify(state.plan)]);
}
function loadStarterPlan(){let row=query("SELECT plan_json FROM _dataforge_queries WHERE name='Sample Revenue by Customer'").rows[0];if(row){try{state.plan=JSON.parse(row[0])}catch(e){}}}
function bind(){
 $$('[data-tab]').forEach(b=>b.onclick=()=>showTab(b.dataset.tab));
 $$('[data-action]').forEach(b=>b.onclick=()=>actions[b.dataset.action]?.());
 $('#fileInput').onchange=e=>importFile(e.target.files[0]); $('#dbInput').onchange=e=>openDb(e.target.files[0]);
 $('#mainTable').onchange=e=>{state.plan.main=e.target.value;state.plan.joins=[];render()};
 $('#distinct').onchange=e=>{state.plan.distinct=e.target.checked;updateSql()}; $('#limit').onchange=e=>{state.plan.limit=+e.target.value||0;updateSql()};
}
function showTab(id){$$('nav button').forEach(x=>x.classList.toggle('active',x.dataset.tab===id));$$('.page').forEach(x=>x.classList.toggle('active',x.id===id));if(id==='chart')setTimeout(drawChart,30)}
function tables(){return query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_dataforge_%' ORDER BY name").rows.map(x=>x[0])}
function columns(t){return query(`PRAGMA table_info(${q(t)})`).rows.map(r=>({name:r[1],type:r[2]||'TEXT'}))}
function query(sql,params=[]){let st=state.db.prepare(sql);st.bind(params);let rows=[];while(st.step())rows.push(st.get());let columns=st.getColumnNames();st.free();return{columns,rows}}
function uniqueTable(raw){let base=clean(raw||'imported_data'),n=2,name=base,T=new Set(tables());while(T.has(name))name=base+'_'+n++;return name}
function infer(vals){vals=vals.filter(x=>x!==null&&x!==undefined&&x!=='');if(!vals.length)return'TEXT';if(vals.every(x=>String(+x)===String(x).trim()&&Number.isInteger(+x)))return'INTEGER';if(vals.every(x=>!isNaN(+x)))return'REAL';return'TEXT'}
function csvParse(text,delim){
 let rows=[],row=[],cell='',quote=false;delim=delim||((text.match(/\t/g)||[]).length>(text.match(/,/g)||[]).length?'\t':',');
 for(let i=0;i<text.length;i++){let c=text[i];if(c==='"'){if(quote&&text[i+1]==='"'){cell+='"';i++}else quote=!quote}else if(c===delim&&!quote){row.push(cell);cell=''}else if((c==='\n'||c==='\r')&&!quote){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(x=>x!==''))rows.push(row);row=[];cell=''}else cell+=c}row.push(cell);if(row.some(x=>x!==''))rows.push(row);if(!rows.length)return[];
 let heads=rows.shift().map((h,i)=>h.trim()||'field_'+(i+1));return rows.map(r=>Object.fromEntries(heads.map((h,i)=>[h,r[i]??''])));
}
async function importFile(file){if(!file)return;try{let text=await file.text(),records;if(file.name.toLowerCase().endsWith('.json')){let x=JSON.parse(text);if(!Array.isArray(x)&&x&&typeof x==='object'){let a=Object.values(x).find(Array.isArray);x=a||[x]}if(!Array.isArray(x))x=[{value:x}];records=x.map(v=>v&&typeof v==='object'&&!Array.isArray(v)?v:{value:v})}else records=csvParse(text);if(!records.length)throw Error('No records found');let name=uniqueTable(file.name.replace(/\.[^.]+$/,''));insertRecords(name,records);if(!state.plan.main)state.plan.main=name;await persist();render();status(`Imported ${records.length} rows into ${name}`)}catch(e){alert('Import failed: '+e.message)}finally{$('#fileInput').value=''}}
function insertRecords(name,records){let keys=[];records.forEach(r=>Object.keys(r).forEach(k=>{if(!keys.includes(k))keys.push(k)}));let map={},used=new Set;keys.forEach((k,i)=>{let n=clean(k||'field_'+i),b=n,j=2;while(used.has(n.toLowerCase()))n=b+'_'+j++;used.add(n.toLowerCase());map[k]=n});let defs=keys.map(k=>q(map[k])+' '+infer(records.slice(0,300).map(r=>r[k])));state.db.run(`CREATE TABLE ${q(name)} (${defs.join(',')})`);let st=state.db.prepare(`INSERT INTO ${q(name)} (${keys.map(k=>q(map[k])).join(',')}) VALUES (${keys.map(()=>'?').join(',')})`);state.db.run('BEGIN');try{records.forEach(r=>{st.run(keys.map(k=>typeof r[k]==='object'&&r[k]!==null?JSON.stringify(r[k]):r[k]??null))});state.db.run('COMMIT')}catch(e){state.db.run('ROLLBACK');throw e}finally{st.free()}}
function render(){let T=tables();$('#mainTable').innerHTML='<option value="">Choose main table</option>'+T.map(t=>`<option ${t===state.plan.main?'selected':''}>${esc(t)}</option>`).join('');$('#distinct').checked=state.plan.distinct;$('#limit').value=state.plan.limit;renderGrid(T);renderTransforms();updateSql();dbSize()}
function renderGrid(T){let linked=new Set(state.plan.joins.map(j=>j.table));$('#grid').innerHTML=T.length?T.map(t=>`<article class="table-card ${t===state.plan.main?'main':linked.has(t)?'linked':''}"><div class="table-title" data-main="${attr(t)}"><span>${t===state.plan.main?'MAIN · ':''}${esc(t)}</span><small>${columns(t).length} cols</small></div>${columns(t).map(c=>`<div class="col ${state.pick===t+'.'+c.name?'picked':''}" data-col="${attr(t+'.'+c.name)}"><i class="port"></i><span>${esc(c.name)}</span><em>${esc(c.type)}</em></div>`).join('')}</article>`).join(''):'<div class="empty">Import CSV/JSON or create a blank table to begin.</div>';$$('[data-main]').forEach(x=>x.onclick=()=>{state.plan.main=x.dataset.main;state.plan.joins=[];render()});$$('[data-col]').forEach(x=>x.onclick=()=>pickColumn(x.dataset.col))}
function pickColumn(r){if(!state.plan.main){state.plan.main=r.split('.')[0];render();return}if(!state.pick){state.pick=r;status('Selected '+r+' — tap a column in another table');renderGrid(tables());return}let a=state.pick,b=r;state.pick=null,ta=a.split('.')[0],tb=b.split('.')[0];if(ta===tb){status('Choose a column in a different table');render();return}let active=new Set([state.plan.main,...state.plan.joins.map(j=>j.table)]),newT=!active.has(tb)?tb:!active.has(ta)?ta:null;if(!newT){status('Those tables are already connected');render();return}let kind=prompt('Join type: LEFT or INNER','LEFT')?.toUpperCase();if(!['LEFT','INNER'].includes(kind))kind='LEFT';state.plan.joins.push({table:newT,left:newT===tb?a:b,right:newT===tb?b:a,kind});render();status(`Connected ${a} to ${b}`)}
function refs(){return[state.plan.main,...state.plan.joins.map(j=>j.table)].filter(Boolean).flatMap(t=>columns(t).map(c=>t+'.'+c.name))}
function choose(promptText,items){if(!items.length){alert('No columns available');return null}let listing=items.map((x,i)=>`${i+1}. ${x}`).join('\n'),raw=prompt(promptText+'\n\n'+listing,'1');if(raw===null)return null;let i=parseInt(raw)-1;return items[i]??(items.includes(raw)?raw:null)}
function renderTransforms(){
 $('#joins').innerHTML=chips(state.plan.joins,j=>`${j.kind} ${j.table}<br>${j.left} = ${j.right}`,'join');
 $('#outputs').innerHTML=chips(state.plan.outputs,o=>`${o.agg?o.agg+' ':''}${o.ref}${o.alias?' → '+o.alias:''}`,'output');
 $('#filters').innerHTML=chips(state.plan.filters,f=>`${f.ref} ${f.op} ${f.value??''}`,'filter');
 let gs=state.plan.groups.map(ref=>({text:'GROUP '+ref})).concat(state.plan.sorts.map(s=>({text:'SORT '+s.ref+' '+s.dir})));$('#groups').innerHTML=gs.length?gs.map(x=>`<div class="chip">${esc(x.text)}</div>`).join(''):'<div class="empty">None</div>';
 $$('.chip button[data-kind]').forEach(b=>b.onclick=()=>{state.plan[b.dataset.kind+'s'].splice(+b.dataset.i,1);render()})
}
function chips(arr,label,kind){return arr.length?arr.map((x,i)=>`<div class="chip ${kind}"><span>${esc(label(x))}</span><button data-kind="${kind}" data-i="${i}">×</button></div>`).join(''):'<div class="empty">None</div>'}
function buildSQL(noLimit=false){let p=state.plan;if(!p.main)throw Error('Choose a main table');let select=p.outputs.length?p.outputs.map(o=>{let x=ref(o.ref);if(o.agg)x=o.agg+'('+x+')';if(o.alias)x+=' AS '+q(clean(o.alias));return x}).join(', '):q(p.main)+'.*'+p.joins.map(j=>', '+q(j.table)+'.*').join('');let sql='SELECT '+(p.distinct?'DISTINCT ':'')+select+'\nFROM '+q(p.main),params=[];p.joins.forEach(j=>sql+=`\n${j.kind} JOIN ${q(j.table)} ON ${ref(j.left)} = ${ref(j.right)}`);if(p.filters.length){sql+='\nWHERE ';p.filters.forEach((f,i)=>{if(i)sql+=' '+(f.conj||'AND')+' ';let op=f.op.toUpperCase();if(op==='IS NULL'||op==='IS NOT NULL')sql+=ref(f.ref)+' '+op;else if(op==='IN'){let vals=String(f.value).split(',').map(x=>x.trim()).filter(Boolean);sql+=ref(f.ref)+' IN ('+vals.map(()=>'?').join(',')+')';params.push(...vals)}else{sql+=ref(f.ref)+' '+op+' ?';params.push(f.value)}})}if(p.groups.length)sql+='\nGROUP BY '+p.groups.map(ref).join(', ');if(p.sorts.length)sql+='\nORDER BY '+p.sorts.map(s=>ref(s.ref)+' '+s.dir).join(', ');if(!noLimit&&p.limit>0)sql+='\nLIMIT '+Math.floor(p.limit);return{sql,params}}
function updateSql(){try{let x=buildSQL();$('#sqlText').textContent=x.sql+(x.params.length?'\n\n-- Parameters: '+JSON.stringify(x.params):'')}catch(e){$('#sqlText').textContent='-- '+e.message}}
function run(){try{let x=buildSQL();state.result=query(x.sql,x.params);renderResult();setupChart();showTab('result');status(`${state.result.rows.length} result rows`)}catch(e){alert('Query failed: '+e.message)}}
function renderResult(){let R=state.result;$('#resultCount').textContent=R.rows.length+' rows';$('#resultTable').innerHTML=R.columns.length?`<table><thead><tr>${R.columns.map(x=>'<th>'+esc(x)+'</th>').join('')}</tr></thead><tbody>${R.rows.slice(0,2000).map(r=>'<tr>'+r.map(v=>'<td>'+esc(v==null?'':typeof v==='object'?JSON.stringify(v):v)+'</td>').join('')+'</tr>').join('')}</tbody></table>`:'<div class="empty">No result</div>'}
const actions={
 import:()=>{$('#sheet').classList.remove('open');$('#fileInput').click()},blank:()=>{$('#sheet').classList.remove('open');createBlank()},run,menu:()=>$('#sheet').classList.add('open'),closeSheet:()=>$('#sheet').classList.remove('open'),
 addJoin(){let T=tables().filter(t=>t!==state.plan.main&&!state.plan.joins.some(j=>j.table===t)),t=choose('Table to join',T);if(!t)return;let l=choose('Existing-side column',refs()),r=choose('Joined-table column',columns(t).map(c=>t+'.'+c.name));if(l&&r){state.plan.joins.push({table:t,left:l,right:r,kind:(prompt('LEFT or INNER join?','LEFT')||'LEFT').toUpperCase()==='INNER'?'INNER':'LEFT'});render()}},
 addColumn(){let r=choose('Output column',refs());if(!r)return;let agg=(prompt('Aggregation: blank, COUNT, SUM, AVG, MIN, MAX, GROUP_CONCAT','')||'').toUpperCase(),alias=prompt('Rename output (optional)','')||'';if(!['','COUNT','SUM','AVG','MIN','MAX','GROUP_CONCAT'].includes(agg))agg='';state.plan.outputs.push({ref:r,agg,alias});render()},
 addFilter(){let r=choose('Filter column',refs());if(!r)return;let op=(prompt('Operator: = != > >= < <= LIKE NOT LIKE IS NULL IS NOT NULL IN','=')||'=').toUpperCase(),value=['IS NULL','IS NOT NULL'].includes(op)?'':prompt('Value (IN: comma separated)','')??'';state.plan.filters.push({ref:r,op,value,conj:'AND'});render()},
 group(){let r=choose('Group by column',refs());if(r&&!state.plan.groups.includes(r)){state.plan.groups.push(r);render()}},sort(){let r=choose('Sort column',refs());if(r){state.plan.sorts.push({ref:r,dir:(prompt('ASC or DESC','ASC')||'ASC').toUpperCase()==='DESC'?'DESC':'ASC'});render()}},
 saveQuery(){let name=prompt('Query name',state.plan.name);if(!name)return;state.plan.name=name;state.db.run('INSERT OR REPLACE INTO _dataforge_queries(name,plan_json,updated_at) VALUES(?,?,CURRENT_TIMESTAMP)',[name,JSON.stringify(state.plan)]);persist();status('Query saved')},
 savedQueries(){let r=query('SELECT name,plan_json FROM _dataforge_queries ORDER BY updated_at DESC').rows;if(!r.length)return alert('No saved queries');let n=choose('Load saved query',r.map(x=>x[0])),row=r.find(x=>x[0]===n);if(row){state.plan=JSON.parse(row[1]);render();$('#sheet').classList.remove('open')}},
 materialize(){try{let raw=prompt('New table name','assembled_output');if(raw===null)return;let n=clean(raw);let x=buildSQL(true);if(tables().includes(n)){if(!confirm(n+' exists. Replace it?'))return;state.db.run('DROP TABLE '+q(n))}state.db.run(`CREATE TABLE ${q(n)} AS ${x.sql}`,x.params);persist();render();status('Saved result as '+n)}catch(e){alert(e.message)}},
 exportCsv:()=>exportResult('csv'),exportJson:()=>exportResult('json'),copySql:()=>copyText($('#sqlText').textContent),drawChart,
 newProject(){if(confirm('Create a new empty project? Export the current database first if needed.')){state.db.close();state.db=new window.SQL.Database();state.plan={name:'Untitled Work Table',main:'',joins:[],outputs:[],filters:[],groups:[],sorts:[],distinct:false,limit:1000};state.result={columns:[],rows:[]};meta();persist();render();$('#sheet').classList.remove('open')}},
 exportDb(){downloadBlob(new Blob([state.db.export()],{type:'application/vnd.sqlite3'}),'dataforge_project.sqlite');status('SQLite database exported')},importDb:()=>$('#dbInput').click()
};
function createBlank(){let rawName=prompt('Table name','new_table');if(rawName===null)return;let name=uniqueTable(rawName);let raw=prompt('Columns, one per line: name, type','id, INTEGER PRIMARY KEY\nname, TEXT\nvalue, REAL');if(raw===null)return;let defs=raw.split('\n').filter(Boolean).map(line=>{let[a,...b]=line.split(',');let typ=(b.join(',').trim()||'TEXT').toUpperCase();if(!['TEXT','INTEGER','REAL','BLOB','NUMERIC','INTEGER PRIMARY KEY'].includes(typ))typ='TEXT';return q(clean(a))+' '+typ});if(!defs.length)defs=[q('id')+' INTEGER PRIMARY KEY'];try{state.db.run(`CREATE TABLE ${q(name)} (${defs.join(',')})`);if(!state.plan.main)state.plan.main=name;persist();render()}catch(e){alert(e.message)}}
async function openDb(file){if(!file)return;try{state.db.close();state.db=new window.SQL.Database(new Uint8Array(await file.arrayBuffer()));meta();state.plan={name:'Untitled Work Table',main:'',joins:[],outputs:[],filters:[],groups:[],sorts:[],distinct:false,limit:1000};await persist();render();$('#sheet').classList.remove('open');status('Opened '+file.name)}catch(e){alert('Could not open database: '+e.message)}finally{$('#dbInput').value=''}}
function exportResult(type){let R=state.result;if(!R.columns.length)return alert('Run a query first');let text,mime;if(type==='json'){text=JSON.stringify(R.rows.map(r=>Object.fromEntries(R.columns.map((c,i)=>[c,r[i]]))),null,2);mime='application/json'}else{text=[R.columns,...R.rows].map(r=>r.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\r\n');mime='text/csv'}downloadBlob(new Blob([text],{type:mime}),'dataforge_output.'+type)}
async function downloadBlob(blob,name){let file=new File([blob],name,{type:blob.type});if(navigator.canShare?.({files:[file]})){try{await navigator.share({files:[file],title:name});status('Export ready');return}catch(e){if(e.name==='AbortError')return}}let a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.append(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},1500)}
function copyText(text){if(navigator.clipboard)navigator.clipboard.writeText(text).then(()=>status('Copied'));else{let t=document.createElement('textarea');t.value=text;document.body.append(t);t.select();document.execCommand('copy');t.remove();status('Copied')}}
function setupChart(){let C=state.result.columns;$('#chartLabel').innerHTML=C.map((x,i)=>`<option value="${i}">${esc(x)}</option>`).join('');$('#chartValue').innerHTML=C.map((x,i)=>`<option value="${i}" ${i===1?'selected':''}>${esc(x)}</option>`).join('')}
function drawChart(){let cvs=$('#chartCanvas'),box=cvs.getBoundingClientRect(),dpr=devicePixelRatio||1;cvs.width=box.width*dpr;cvs.height=box.height*dpr;let c=cvs.getContext('2d');c.scale(dpr,dpr);let w=box.width,h=box.height;c.clearRect(0,0,w,h);let rows=state.result.rows.slice(0,24),li=+$('#chartLabel').value||0,vi=+$('#chartValue').value||1,type=$('#chartType').value,data=rows.map(r=>({l:String(r[li]??''),v:+r[vi]||0}));if(!data.length){c.fillStyle='#8ea3c7';c.fillText('Run a query, then choose chart columns.',20,30);return}let colors=['#22d3ee','#a78bfa','#34d399','#fbbf24','#fb7185'];if(type==='pie'){let total=data.reduce((a,x)=>a+Math.abs(x.v),0)||1,a=-Math.PI/2,R=Math.min(w,h)*.33;data.forEach((x,i)=>{let n=Math.abs(x.v)/total*Math.PI*2;c.beginPath();c.moveTo(w/2,h/2);c.arc(w/2,h/2,R,a,a+n);c.fillStyle=colors[i%colors.length];c.fill();a+=n});data.slice(0,8).forEach((x,i)=>{c.fillStyle=colors[i%colors.length];c.fillRect(12,12+i*20,10,10);c.fillStyle='#e9f1ff';c.fillText(x.l.slice(0,18),28,22+i*20)});return}let max=Math.max(...data.map(x=>Math.abs(x.v)),1),pad=42,step=(w-pad*2)/data.length;c.strokeStyle='#334765';c.beginPath();c.moveTo(pad,h-pad);c.lineTo(w-pad,h-pad);c.stroke();if(type==='line'){c.strokeStyle='#22d3ee';c.lineWidth=3;c.beginPath();data.forEach((x,i)=>{let px=pad+i*step+step/2,py=h-pad-(h-pad*2)*x.v/max;i?c.lineTo(px,py):c.moveTo(px,py)});c.stroke()}else data.forEach((x,i)=>{let bh=(h-pad*2)*Math.abs(x.v)/max;c.fillStyle=colors[i%colors.length];c.fillRect(pad+i*step+3,h-pad-bh,Math.max(4,step-7),bh)});c.fillStyle='#8ea3c7';c.font='10px system-ui';data.forEach((x,i)=>{c.save();c.translate(pad+i*step+step/2,h-pad+6);c.rotate(.6);c.fillText(x.l.slice(0,12),0,0);c.restore()})}
async function persist(){let b=state.db.export();await idbSet('database',b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength));dbSize()}
function idb(){return new Promise((ok,no)=>{let r=indexedDB.open('DataForge',1);r.onupgradeneeded=()=>r.result.createObjectStore('files');r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)})}
async function idbGet(k){let d=await idb();return new Promise((ok,no)=>{let r=d.transaction('files').objectStore('files').get(k);r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)})}
async function idbSet(k,v){let d=await idb();return new Promise((ok,no)=>{let r=d.transaction('files','readwrite').objectStore('files').put(v,k);r.onsuccess=()=>ok();r.onerror=()=>no(r.error)})}
function dbSize(){if(!state.db)return;let n=state.db.export().length;$('#dbSize').textContent=n<1048576?(n/1024).toFixed(1)+' KB':(n/1048576).toFixed(1)+' MB'}function status(s){$('#status').textContent=s}function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}function attr(s){return esc(s)}
start().catch(e=>{status('Startup error');alert(e.message)});
