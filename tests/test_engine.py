import json, tempfile
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/"desktop"))
from engine import ProjectDB, QueryPlan, Join, Filter, OutputColumn

def main():
    with tempfile.TemporaryDirectory() as d:
        db=ProjectDB(Path(d)/"test.sqlite")
        db.import_records([{"id":1,"name":"Alpha"},{"id":2,"name":"Beta"}],"people")
        db.import_records([{"person_id":1,"amount":10},{"person_id":1,"amount":20},{"person_id":2,"amount":5}],"sales")
        p=QueryPlan(main_table="people",joins=[Join("sales","people.id","sales.person_id","LEFT")],columns=[OutputColumn("people.name"),OutputColumn("sales.amount","total","SUM")],group_by=["people.name"],order_by=[("total","DESC")])
        cols,rows=db.execute_plan(p)
        assert cols==["name","total"] and rows[0]==("Alpha",30), (cols,rows)
        p.filters=[Filter("people.name","LIKE","A%")]
        assert len(db.execute_plan(p)[1])==1
        out=db.materialize(p,"summary")
        assert out in db.tables()
        db.save_plan(p); assert db.load_plan(p.name).main_table=="people"
        db.close()
    print("engine tests: PASS")

if __name__=="__main__": main()
