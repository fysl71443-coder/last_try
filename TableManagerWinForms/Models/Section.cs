using System.Collections.Generic;

namespace TableManagerWinForms.Models
{
    public class Section
    {
        public string Name { get; set; }

        public List<Table> Tables { get; set; }

        public Section()
        {
            Name = string.Empty;
            Tables = new List<Table>();
        }

        public Section(string name)
        {
            Name = name;
            Tables = new List<Table>();
        }
    }
}


