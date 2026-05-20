from pathlib import Path

from openpyxl import Workbook

from resume_screening.job_requirements import load_job_requirements


def make_job_book(path: Path) -> None:
    workbook = Workbook()
    template = workbook.active
    template.title = "模板"
    template["A1"] = "岗位说明书"
    product = workbook.create_sheet("产品总监")
    product.append(["岗位说明书"])
    product.append([None, None, None, None, None, None, None, "HR(03)20260001"])
    product.append(["一、基本信息"])
    product.append(["岗位名称", "技术产品总监", "所属部门", "研发部", "直接上级", "郑廉", "岗位等级", None])
    product.append(["岗位编制", "1/1", "岗位性质", "全职", None, None, "职级", "总监"])
    product.append(["工作地点", "北京", "工作方式", "半线上", None, None, "工作经验", "8年以上"])
    product.append(["学历", "统招本科及以上", "专业", "计算机、信息工程", "证书持有", "", "技能/素质", "AI产品、Agent"])
    product.append(["语言要求", "普通话", None, None, "晋升路径", "", None, None])
    product.append(["二、岗位目的"])
    product.append(["具体描述", "负责AI产品规划和跨团队落地。"])
    product.append(["三、主要工作职责及核心考核指标"])
    product.append(["1. 核心职责", "负责产品路线图和核心指标。"])
    product.append(["2. 核心职责", "推动研发、算法、运营协同。"])
    product.append(["3. 核心职责", "建立产品数据反馈机制。"])
    product.append(["4. 补充职责", "有Agent经验优先。"])
    product.append(["四、其他说明"])
    product.append(["补充说明", "无"])
    empty = workbook.create_sheet("算法")
    empty.append(["岗位说明书"])
    empty.append(["一、基本信息"])
    workbook.save(path)


def test_load_job_requirements_ignores_template_and_detects_completeness(tmp_path: Path) -> None:
    path = tmp_path / "jobs.xlsx"
    make_job_book(path)

    jobs = load_job_requirements(path)

    assert "模板" not in jobs
    assert jobs["产品总监"].is_complete is True
    assert "负责AI产品规划" in jobs["产品总监"].raw_text
    assert jobs["算法"].is_complete is False
    assert "岗位名称" in jobs["算法"].missing_fields


def test_load_job_requirements_supports_tabular_job_rows(tmp_path: Path) -> None:
    path = tmp_path / "jobs.xlsx"
    workbook = Workbook()
    template = workbook.active
    template.title = "模板"
    sheet = workbook.create_sheet("后端开发")
    sheet.append(["岗位名称", "岗位别名", "岗位性质", "学历要求", "工作年限要求", "工作经验要求", "核心职责1", "核心职责2", "岗位jd"])
    sheet.append([
        "后端开发",
        "Java开发",
        "实习",
        "本科、硕士、博士",
        "26、27届毕业生",
        "0到1年",
        "Java后端开发",
        "Spring Cloud / Spring Boot",
        "负责医者核心业务后端开发。",
    ])
    sheet.append([
        "AI产品经理",
        "AI交互产品经理",
        "实习或全职",
        "本科、硕士、博士",
        "26、27届毕业生",
        "0-2年",
        "海外TOC产品",
        "AI交互设计",
        "负责ToC端AI交互产品规划。",
    ])
    workbook.save(path)

    jobs = load_job_requirements(path)

    assert jobs["后端开发"].is_complete is True
    assert jobs["后端开发"].sheet_name == "后端开发"
    assert jobs["后端开发"].fields["岗位别名"] == "Java开发"
    assert "Spring Cloud" in jobs["后端开发"].raw_text
    assert jobs["AI产品经理"].is_complete is True
    assert "AI交互产品经理" in jobs["AI产品经理"].raw_text
