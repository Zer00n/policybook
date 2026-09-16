from fastapi.testclient import TestClient
from app.db.models import Member
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)



def test_member_crud_and_placeholder():
    # 清理测试表以保证单测独立性
    db = SessionLocal()
    db.query(Member).delete()
    db.commit()
    db.close()

    # 1. 创建成员 A
    res1 = client.post(
        "/api/members",
        json={
            "display_name": "爸爸",
            "relation": "本人",
            "birth_year": 1980,
            "gender": "男",
            "occupation": "软件工程师",
            "city": "北京",
            "social_insurance": "职工",
            "real_name": "张伟明",
        },
    )
    assert res1.status_code == 201
    m1 = res1.json()
    assert m1["placeholder"] == "〔成员A〕"
    assert m1["display_name"] == "爸爸"
    assert m1["real_name"] == "张伟明"

    # 2. 创建成员 B
    res2 = client.post(
        "/api/members",
        json={
            "display_name": "儿子",
            "relation": "子女",
            "birth_year": 2012,
            "gender": "男",
            "real_name": "张伟",
        },
    )
    assert res2.status_code == 201
    m2 = res2.json()
    assert m2["placeholder"] == "〔成员B〕"

    # 3. 列表查询
    list_res = client.get("/api/members")
    assert list_res.status_code == 200
    members = list_res.json()
    assert len(members) >= 2

    # 4. 更新成员
    patch_res = client.patch(
        f"/api/members/{m1['id']}",
        json={"occupation": "高级架构师"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["occupation"] == "高级架构师"

    # 5. 删除成员
    del_res = client.delete(f"/api/members/{m2['id']}")
    assert del_res.status_code == 200
    assert del_res.json()["ok"] is True
