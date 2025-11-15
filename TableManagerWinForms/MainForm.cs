using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;
using TableManagerWinForms.Models;

namespace TableManagerWinForms
{
    public class MainForm : Form
    {
        private readonly List<Section> _originalSections;
        private List<Section> _workingSections;

        private readonly SplitContainer _split;
        private readonly ListBox _sectionsListBox;
        private readonly TextBox _sectionNameTextBox;
        private readonly Button _addSectionButton;
        private readonly Button _deleteSectionButton;

        private readonly TableLayoutPanel _grid;

        private readonly GroupBox _controlsBox;
        private readonly TextBox _tableLabelTextBox;
        private readonly NumericUpDown _rowUpDown;
        private readonly NumericUpDown _colUpDown;
        private readonly Button _addTableButton;
        private readonly NumericUpDown _deleteRowUpDown;
        private readonly NumericUpDown _deleteColUpDown;
        private readonly Button _deleteRowButton;
        private readonly Button _deleteColButton;
        private readonly Button _saveButton;
        private readonly Button _cancelButton;

        public MainForm()
        {
            Text = "Table Manager - Sections & Tables";
            Width = 1200;
            Height = 800;

            _originalSections = CreateSeedData();
            _workingSections = DeepCopy(_originalSections);

            _split = new SplitContainer
            {
                Dock = DockStyle.Fill,
                Orientation = Orientation.Vertical,
                SplitterDistance = 300
            };
            Controls.Add(_split);

            // Left panel: sections management
            var leftPanel = new Panel { Dock = DockStyle.Fill, Padding = new Padding(8) };
            _split.Panel1.Controls.Add(leftPanel);

            var sectionsLabel = new Label { Text = "Sections", Dock = DockStyle.Top, Height = 24 };
            leftPanel.Controls.Add(sectionsLabel);

            _sectionsListBox = new ListBox { Dock = DockStyle.Top, Height = 300 };
            leftPanel.Controls.Add(_sectionsListBox);

            var sectionEditorPanel = new FlowLayoutPanel
            {
                Dock = DockStyle.Top,
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                Padding = new Padding(0),
                Margin = new Padding(0)
            };
            _sectionNameTextBox = new TextBox { Width = 160, PlaceholderText = "Section name" };
            _addSectionButton = new Button { Text = "Add Section" };
            _deleteSectionButton = new Button { Text = "Delete Section" };
            sectionEditorPanel.Controls.Add(_sectionNameTextBox);
            sectionEditorPanel.Controls.Add(_addSectionButton);
            sectionEditorPanel.Controls.Add(_deleteSectionButton);
            leftPanel.Controls.Add(sectionEditorPanel);

            // Right panel: grid and controls
            var rightPanel = new Panel { Dock = DockStyle.Fill, Padding = new Padding(8) };
            _split.Panel2.Controls.Add(rightPanel);

            _grid = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                CellBorderStyle = TableLayoutPanelCellBorderStyle.Single,
                BackColor = Color.White
            };

            _controlsBox = new GroupBox
            {
                Dock = DockStyle.Top,
                Height = 140,
                Text = "Controls"
            };

            var controlsFlow = new FlowLayoutPanel
            {
                Dock = DockStyle.Fill,
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents = true
            };
            _controlsBox.Controls.Add(controlsFlow);

            _tableLabelTextBox = new TextBox { Width = 120, PlaceholderText = "Table label" };
            _rowUpDown = new NumericUpDown { Minimum = 0, Maximum = 1000, Width = 60 };
            _colUpDown = new NumericUpDown { Minimum = 0, Maximum = 1000, Width = 60 };
            _addTableButton = new Button { Text = "Add Table" };

            _deleteRowUpDown = new NumericUpDown { Minimum = 0, Maximum = 1000, Width = 60 };
            _deleteColUpDown = new NumericUpDown { Minimum = 0, Maximum = 1000, Width = 60 };
            _deleteRowButton = new Button { Text = "Delete Row" };
            _deleteColButton = new Button { Text = "Delete Column" };

            _saveButton = new Button { Text = "Save", Width = 80 };
            _cancelButton = new Button { Text = "Cancel", Width = 80 };

            controlsFlow.Controls.Add(new Label { Text = "Label:" });
            controlsFlow.Controls.Add(_tableLabelTextBox);
            controlsFlow.Controls.Add(new Label { Text = "Row:" });
            controlsFlow.Controls.Add(_rowUpDown);
            controlsFlow.Controls.Add(new Label { Text = "Col:" });
            controlsFlow.Controls.Add(_colUpDown);
            controlsFlow.Controls.Add(_addTableButton);
            controlsFlow.Controls.Add(new Label { Text = "Del Row:" });
            controlsFlow.Controls.Add(_deleteRowUpDown);
            controlsFlow.Controls.Add(_deleteRowButton);
            controlsFlow.Controls.Add(new Label { Text = "Del Col:" });
            controlsFlow.Controls.Add(_deleteColUpDown);
            controlsFlow.Controls.Add(_deleteColButton);
            controlsFlow.Controls.Add(_saveButton);
            controlsFlow.Controls.Add(_cancelButton);

            rightPanel.Controls.Add(_grid);
            rightPanel.Controls.Add(_controlsBox);

            // Events
            Load += (_, __) => InitializeUi();
            _sectionsListBox.SelectedIndexChanged += (_, __) => RefreshGrid();
            _addSectionButton.Click += (_, __) => AddSection();
            _deleteSectionButton.Click += (_, __) => DeleteSelectedSection();
            _addTableButton.Click += (_, __) => AddTableToCurrentSection();
            _deleteRowButton.Click += (_, __) => DeleteRowFromCurrentSection();
            _deleteColButton.Click += (_, __) => DeleteColumnFromCurrentSection();
            _saveButton.Click += (_, __) => SaveChanges();
            _cancelButton.Click += (_, __) => CancelChanges();
        }

        private void InitializeUi()
        {
            RefreshSectionsList();
            if (_sectionsListBox.Items.Count > 0)
            {
                _sectionsListBox.SelectedIndex = 0;
            }
        }

        private void RefreshSectionsList()
        {
            _sectionsListBox.Items.Clear();
            foreach (var section in _workingSections)
            {
                _sectionsListBox.Items.Add(section.Name);
            }
        }

        private Section? GetSelectedSection()
        {
            var index = _sectionsListBox.SelectedIndex;
            if (index < 0 || index >= _workingSections.Count)
            {
                return null;
            }
            return _workingSections[index];
        }

        private void RefreshGrid()
        {
            var section = GetSelectedSection();
            _grid.SuspendLayout();
            _grid.Controls.Clear();
            _grid.RowStyles.Clear();
            _grid.ColumnStyles.Clear();
            _grid.RowCount = 0;
            _grid.ColumnCount = 0;

            if (section == null)
            {
                _grid.ResumeLayout();
                return;
            }

            var maxRow = section.Tables.Count == 0 ? 0 : section.Tables.Max(t => t.RowIndex);
            var maxCol = section.Tables.Count == 0 ? 0 : section.Tables.Max(t => t.ColumnIndex);

            _grid.RowCount = maxRow + 1;
            _grid.ColumnCount = maxCol + 1;

            for (int r = 0; r < _grid.RowCount; r++)
            {
                _grid.RowStyles.Add(new RowStyle(SizeType.Percent, 100f / Math.Max(1, _grid.RowCount)));
            }
            for (int c = 0; c < _grid.ColumnCount; c++)
            {
                _grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f / Math.Max(1, _grid.ColumnCount)));
            }

            // Place buttons for tables; empty cells remain placeholders
            foreach (var table in section.Tables)
            {
                var btn = new Button
                {
                    Text = table.Label,
                    Dock = DockStyle.Fill,
                    BackColor = Color.LightSteelBlue,
                    Tag = table
                };
                _grid.Controls.Add(btn, table.ColumnIndex, table.RowIndex);
            }

            _grid.ResumeLayout();
        }

        private void AddSection()
        {
            var name = _sectionNameTextBox.Text.Trim();
            if (string.IsNullOrWhiteSpace(name))
            {
                MessageBox.Show("Enter a section name.");
                return;
            }
            if (_workingSections.Any(s => string.Equals(s.Name, name, StringComparison.OrdinalIgnoreCase)))
            {
                MessageBox.Show("Section with this name already exists.");
                return;
            }
            _workingSections.Add(new Section(name));
            _sectionNameTextBox.Clear();
            RefreshSectionsList();
            _sectionsListBox.SelectedIndex = _workingSections.Count - 1;
        }

        private void DeleteSelectedSection()
        {
            var index = _sectionsListBox.SelectedIndex;
            if (index < 0)
            {
                MessageBox.Show("Select a section to delete.");
                return;
            }
            var name = _workingSections[index].Name;
            var result = MessageBox.Show($"Delete section '{name}' and all its tables?", "Confirm", MessageBoxButtons.YesNo);
            if (result == DialogResult.Yes)
            {
                _workingSections.RemoveAt(index);
                RefreshSectionsList();
                RefreshGrid();
            }
        }

        private void AddTableToCurrentSection()
        {
            var section = GetSelectedSection();
            if (section == null)
            {
                MessageBox.Show("Select a section first.");
                return;
            }
            var label = _tableLabelTextBox.Text.Trim();
            if (string.IsNullOrWhiteSpace(label))
            {
                MessageBox.Show("Enter table label/number.");
                return;
            }

            int row = (int)_rowUpDown.Value;
            int col = (int)_colUpDown.Value;

            // Ensure unique position; allow overwriting if user confirms
            var existing = section.Tables.FirstOrDefault(t => t.RowIndex == row && t.ColumnIndex == col);
            if (existing != null)
            {
                var overwrite = MessageBox.Show("Cell already has a table. Replace?", "Confirm", MessageBoxButtons.YesNo);
                if (overwrite != DialogResult.Yes)
                {
                    return;
                }
                section.Tables.Remove(existing);
            }

            section.Tables.Add(new Table(label, row, col));
            _tableLabelTextBox.Clear();
            RefreshGrid();
        }

        private void DeleteRowFromCurrentSection()
        {
            var section = GetSelectedSection();
            if (section == null)
            {
                MessageBox.Show("Select a section first.");
                return;
            }
            int row = (int)_deleteRowUpDown.Value;
            if (!section.Tables.Any(t => t.RowIndex == row))
            {
                // Deleting an empty row is allowed; just shift rows above? Nothing to do except shifting indices above
            }
            // Remove all tables in the row
            section.Tables.RemoveAll(t => t.RowIndex == row);
            // Shift rows after the deleted row
            foreach (var t in section.Tables)
            {
                if (t.RowIndex > row)
                {
                    t.RowIndex -= 1;
                }
            }
            RefreshGrid();
        }

        private void DeleteColumnFromCurrentSection()
        {
            var section = GetSelectedSection();
            if (section == null)
            {
                MessageBox.Show("Select a section first.");
                return;
            }
            int col = (int)_deleteColUpDown.Value;
            section.Tables.RemoveAll(t => t.ColumnIndex == col);
            foreach (var t in section.Tables)
            {
                if (t.ColumnIndex > col)
                {
                    t.ColumnIndex -= 1;
                }
            }
            RefreshGrid();
        }

        private void SaveChanges()
        {
            _originalSections.Clear();
            _originalSections.AddRange(DeepCopy(_workingSections));
            MessageBox.Show("Changes saved.");
        }

        private void CancelChanges()
        {
            _workingSections = DeepCopy(_originalSections);
            RefreshSectionsList();
            RefreshGrid();
            MessageBox.Show("Changes reverted.");
        }

        private static List<Section> CreateSeedData()
        {
            var s1 = new Section("Main Hall");
            s1.Tables.Add(new Table("T1", 0, 0));
            s1.Tables.Add(new Table("T2", 0, 2));
            s1.Tables.Add(new Table("T3", 1, 1));

            var s2 = new Section("Family Area");
            s2.Tables.Add(new Table("F1", 0, 0));
            s2.Tables.Add(new Table("F2", 0, 1));
            s2.Tables.Add(new Table("F3", 1, 0));

            var s3 = new Section("VIP");
            s3.Tables.Add(new Table("V1", 0, 0));
            s3.Tables.Add(new Table("V2", 1, 1));

            return new List<Section> { s1, s2, s3 };
        }

        private static List<Section> DeepCopy(List<Section> sections)
        {
            return sections.Select(s => new Section(s.Name)
            {
                Tables = s.Tables.Select(t => new Table(t.Label, t.RowIndex, t.ColumnIndex)).ToList()
            }).ToList();
        }
    }
}



