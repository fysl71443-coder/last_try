namespace TableManagerWinForms.Models
{
    public class Table
    {
        public string Label { get; set; }
        public int RowIndex { get; set; }
        public int ColumnIndex { get; set; }

        public Table()
        {
            Label = string.Empty;
        }

        public Table(string label, int rowIndex, int columnIndex)
        {
            Label = label;
            RowIndex = rowIndex;
            ColumnIndex = columnIndex;
        }
    }
}


