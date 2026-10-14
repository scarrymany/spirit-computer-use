using System.Text.Json;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        if (args.Length != 2) return;
        Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
        Application.EnableVisualStyles();
        using var window = new TestWindow(args[0], args[1]);
        Application.Run(window);
    }
}

internal sealed class TestWindow : Form
{
    private readonly string statePath;
    private readonly TextBox editor;
    private readonly CheckBox toggle;
    private int clicks;
    private int dragMoves;
    private int wheel;
    private bool dragging;

    public TestWindow(string title, string path)
    {
        statePath = path;
        Text = title;
        ClientSize = new Size(760, 470);
        StartPosition = FormStartPosition.Manual;
        Location = new Point(120, 120);
        BackColor = Color.FromArgb(19, 22, 31);
        ForeColor = Color.White;
        Font = new Font("Segoe UI", 11);
        Controls.Add(new Label { Text = "SPIRIT / Desktop integration test", AutoSize = true,
            Location = new Point(25, 25), Font = new Font("Segoe UI", 18, FontStyle.Bold) });
        editor = new TextBox { AccessibleName = "SPIRIT editor", Multiline = true,
            Location = new Point(25, 85), Size = new Size(705, 115), Text = "Ready" };
        var button = new Button { Text = "Count click", AccessibleName = "SPIRIT button",
            Location = new Point(25, 220), Size = new Size(160, 45), ForeColor = Color.Black };
        toggle = new CheckBox { Text = "UIA toggle", AccessibleName = "SPIRIT toggle",
            Location = new Point(215, 230), AutoSize = true };
        var pad = new Panel { AccessibleName = "SPIRIT drag pad",
            Location = new Point(25, 290), Size = new Size(705, 145),
            BackColor = Color.FromArgb(48, 39, 71), TabStop = true };
        pad.Paint += (_, e) => e.Graphics.DrawString("Drag and scroll here", Font,
            Brushes.White, new PointF(20, 20));
        Controls.AddRange([editor, button, toggle, pad]);
        editor.TextChanged += (_, _) => Save();
        button.Click += (_, _) => { clicks++; Save(); };
        toggle.CheckedChanged += (_, _) => Save();
        pad.MouseDown += (_, _) => { dragging = true; pad.Focus(); };
        pad.MouseMove += (_, _) => { if (dragging) { dragMoves++; Save(); } };
        pad.MouseUp += (_, _) => { dragging = false; Save(); };
        pad.MouseWheel += (_, e) => { wheel += e.Delta; Save(); };
        Shown += (_, _) => { editor.Focus(); Save(); };
    }

    private void Save()
    {
        var payload = JsonSerializer.Serialize(new {
            hwnd = Handle.ToInt64(), text = editor.Text, clicks, dragMoves, wheel,
            dragging, toggled = toggle.Checked
        });
        using var output = new FileStream(statePath, FileMode.Create, FileAccess.Write,
            FileShare.ReadWrite);
        using var writer = new StreamWriter(output);
        writer.Write(payload);
    }
}
