-- إنشاء القسم الجديد إذا لم يكن موجودًا
INSERT INTO table_sections (branch_code, name, sort_order, created_at, updated_at)
VALUES ('all', 'China Town', 1, now(), now())
ON CONFLICT (branch_code, name) DO NOTHING;

-- إضافة الطاولات وربطها بالقسم
DO $$
DECLARE
    section_id INT;
    tbl_num TEXT;
    table_list TEXT[] := ARRAY[
        '1','2','3','4','5','6','8',
        '10','11','12','30','31','32',
        '40','50','60','61','63','53','43','38',
        '70','71','72','25','26','27','28','29',
        '90','92','93','94','95','105',
        '101','102','103','104'
    ];
BEGIN
    -- احصل على id القسم
    SELECT id INTO section_id
    FROM table_sections
    WHERE branch_code = 'all' AND name = 'China Town';

    -- إدخال الطاولات وربطها بالقسم
    FOREACH tbl_num IN ARRAY table_list LOOP
        -- إدخال الطاولة إذا لم تكن موجودة مسبقًا
        INSERT INTO tables (branch_code, table_number, created_at, updated_at)
        VALUES ('all', tbl_num, now(), now())
        ON CONFLICT (branch_code, table_number) DO NOTHING;

        -- ربط الطاولة بالقسم
        INSERT INTO table_section_assignments (branch_code, table_number, section_id)
        VALUES ('all', tbl_num, section_id)
        ON CONFLICT (branch_code, table_number) DO NOTHING;
    END LOOP;
END $$;
