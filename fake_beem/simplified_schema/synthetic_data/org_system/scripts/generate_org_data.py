import random
import time
import os

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "../data")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

ORG_FILE = os.path.join(OUTPUT_DIR, "org.txt")
USER_FILE = os.path.join(OUTPUT_DIR, "user.txt")
DEPT_FILE = os.path.join(OUTPUT_DIR, "dept.txt")
DEPT_USER_FILE = os.path.join(OUTPUT_DIR, "dept_user.txt")

# Roles
ROLE_PM = 1
ROLE_DEV = 2
ROLE_ALGO = 3
ROLE_HR = 4
ROLE_ANDROID = 5
ROLE_IOS = 6
ROLE_QA = 7
ROLE_L2_LEADER = 8
ROLE_L1_LEADER = 9

# Global Counters
g_user_id = 10001
g_dept_id = 100
g_org_id = 1

# Data Containers
data_org = []
data_user = []
data_dept = []
data_dept_user = []

# Uniqueness Sets
used_mobiles = set()
used_emails = set()

# --- Helper Functions ---

def get_timestamp(year):
    # Middle of the year approx
    return int(time.mktime(time.strptime(f'{year}-06-15', '%Y-%m-%d')))

def generate_mobile():
    while True:
        # 1 + 10 digits to make 11? No, 1 + 2nd digit + 9 digits.
        # prefix 13-19.
        prefix = random.choice([13, 15, 16, 17, 18, 19])
        suffix = random.randint(100000000, 999999999) # 9 digits
        # 2 + 9 = 11 digits.
        s = f"{prefix}{str(suffix)[1:]}" # suffix might be 100... so 9 digits. 
        # Better:
        s = f"{prefix}{random.randint(0,999999999):09d}"
        
        if s not in used_mobiles:
            used_mobiles.add(s)
            return s

def generate_email(org_short):
    while True:
        s = f"u{random.randint(100000, 999999)}@{org_short.lower()}.com"
        if s not in used_emails:
            used_emails.add(s)
            return s

def generate_name():
    first_names = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴鬱胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴衢阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧"
    last_names = "伟刚勇毅俊峰强军平保东文辉力明永健世广志义兴良海山仁波宁贵福生龙元全国胜学祥才发武新利清飞彬富顺信子杰涛昌成康星光天达安岩中茂进林有坚和彪博诚先敬震振壮会思群豪心邦承乐绍功松善厚庆磊民友裕河哲江超浩亮政谦亨奇固之轮翰朗伯宏言若鸣朋斌梁栋维启克伦翔旭鹏泽晨辰士以建家致树炎德行时泰盛雄琛钧冠策腾楠榕风航弘"
    fn = random.choice(first_names)
    ln_len = random.choice([1, 2])
    ln = "".join(random.choice(last_names) for _ in range(ln_len))
    return fn + ln

def create_user(org_id, name, manager_id, role, join_year):
    global g_user_id
    uid = g_user_id
    g_user_id += 1
    
    # Org short name lookup
    org_short = "org"
    for o in data_org:
        if o['id'] == org_id:
            org_short = o['short_name']
            break
            
    mobile = generate_mobile()
    email = generate_email(org_short)
    
    join_date = get_timestamp(join_year)
    gender = random.choice([1, 2])
    birthday = get_timestamp(random.randint(1980, 2000))
    
    u = {
        'id': uid,
        'org_id': org_id,
        'name': name,
        'manager_id': manager_id, # Can be None
        'role': role,
        'mobile': mobile,
        'email': email,
        'join_date': join_date,
        'gender': gender,
        'birthday': birthday
    }
    data_user.append(u)
    return u

def create_dept(org_id, name, parent_id, leader_id, level, created_year):
    global g_dept_id
    did = g_dept_id
    g_dept_id += 1
    
    created_at = get_timestamp(created_year)
    
    d = {
        'id': did,
        'org_id': org_id,
        'name': name,
        'parent_id': parent_id, # None for top level
        'leader_id': leader_id,
        'level': level,
        'created_at': created_at
    }
    data_dept.append(d)
    return d

def link_dept_user(org_id, dept_id, user_id, join_year):
    created_at = get_timestamp(join_year)
    du = {
        'org_id': org_id,
        'dept_id': dept_id,
        'user_id': user_id,
        'created_at': created_at
    }
    data_dept_user.append(du)

# --- Generation Logic ---

def generate_jaco():
    global g_org_id
    org_id = g_org_id
    g_org_id += 1
    
    org_name = "Jaco"
    short_name = "Jaco"
    created_year = 2021
    
    # CEO
    ceo_name = "马云"
    ceo = create_user(org_id, ceo_name, None, 9, created_year)
    
    # Org Entry
    o = {
        'id': org_id,
        'name': org_name,
        'short_name': short_name,
        'owner_user_id': ceo['id'],
        'created_at': get_timestamp(created_year)
    }
    data_org.append(o)
    
    # Departments
    depts_spec = [
        ("机器学习", [ROLE_DEV]*2 + [ROLE_ALGO]*8),
        ("产品", [ROLE_PM]*10),
        ("用户增长", [ROLE_DEV]*2 + [ROLE_ALGO]*8),
        ("前端", [ROLE_ANDROID]*5 + [ROLE_IOS]*5),
        ("后端", [ROLE_DEV]*10),
        ("人力资源", [ROLE_HR]*10)
    ]
    
    for d_name, roles in depts_spec:
        # Leader
        leader_name = generate_name()
        leader = create_user(org_id, leader_name, ceo['id'], ROLE_L1_LEADER, created_year)
        
        # Dept
        dept = create_dept(org_id, d_name, None, leader['id'], 1, created_year)
        link_dept_user(org_id, dept['id'], leader['id'], created_year)
        
        # Members (skip first role as it's taken by leader)
        member_roles = roles[1:]
        
        for r in member_roles:
            m_name = generate_name()
            m = create_user(org_id, m_name, leader['id'], r, created_year)
            link_dept_user(org_id, dept['id'], m['id'], created_year)

def generate_beem():
    global g_org_id
    org_id = g_org_id
    g_org_id += 1
    
    org_name = "Beem"
    short_name = "Beem"
    created_year = 2022
    
    ceo_name = "马化腾"
    ceo = create_user(org_id, ceo_name, None, 9, created_year)
    
    o = {
        'id': org_id,
        'name': org_name,
        'short_name': short_name,
        'owner_user_id': ceo['id'],
        'created_at': get_timestamp(created_year)
    }
    data_org.append(o)
    
    # 1. Depts without L2
    simple_depts = [
        ("产品", [ROLE_PM]*10),
        ("测试", [ROLE_QA]*10),
        ("后端", [ROLE_DEV]*10),
        ("人力资源", [ROLE_HR]*10)
    ]
    
    for d_name, roles in simple_depts:
        leader_name = generate_name()
        leader = create_user(org_id, leader_name, ceo['id'], ROLE_L1_LEADER, created_year)
        
        dept = create_dept(org_id, d_name, None, leader['id'], 1, created_year)
        link_dept_user(org_id, dept['id'], leader['id'], created_year)
        
        member_roles = roles[1:]
        for r in member_roles:
            m_name = generate_name()
            m = create_user(org_id, m_name, leader['id'], r, created_year)
            link_dept_user(org_id, dept['id'], m['id'], created_year)
            
    # 2. Dept with L2: Frontend
    fe_leader_name = generate_name()
    fe_leader = create_user(org_id, fe_leader_name, ceo['id'], ROLE_L1_LEADER, created_year)
    
    fe_dept = create_dept(org_id, "前端", None, fe_leader['id'], 1, created_year)
    link_dept_user(org_id, fe_dept['id'], fe_leader['id'], created_year)
    
    l2_specs = [
        ("web工程", [ROLE_DEV]*5),
        ("ios工程", [ROLE_IOS]*5),
        ("Android工程", [ROLE_ANDROID]*5)
    ]
    
    for l2_name, roles in l2_specs:
        l2_leader_name = generate_name()
        # Reports to L1 Leader
        l2_leader = create_user(org_id, l2_leader_name, fe_leader['id'], ROLE_L2_LEADER, created_year)
        
        l2_dept = create_dept(org_id, l2_name, fe_dept['id'], l2_leader['id'], 2, created_year)
        link_dept_user(org_id, l2_dept['id'], l2_leader['id'], created_year)
        
        member_roles = roles[1:]
        for r in member_roles:
            m_name = generate_name()
            m = create_user(org_id, m_name, l2_leader['id'], r, created_year)
            link_dept_user(org_id, l2_dept['id'], m['id'], created_year)

# --- Output ---
def write_file(filename, headers, data):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("\t".join(headers) + "\n")
        for row in data:
            line = []
            for h in headers:
                val = row.get(h)
                if val is None:
                    val = "" 
                else:
                    val = str(val)
                line.append(val)
            f.write("\t".join(line) + "\n")

if __name__ == "__main__":
    generate_jaco()
    generate_beem()
    
    write_file(ORG_FILE, ["id", "name", "short_name", "owner_user_id", "created_at"], data_org)
    write_file(USER_FILE, ["id", "org_id", "name", "manager_id", "role", "mobile", "email", "join_date", "gender", "birthday"], data_user)
    write_file(DEPT_FILE, ["id", "org_id", "name", "parent_id", "leader_id", "level", "created_at"], data_dept)
    write_file(DEPT_USER_FILE, ["org_id", "dept_id", "user_id", "created_at"], data_dept_user)
