using System.IO;
using System.Windows;
using Microsoft.Win32;
using TaskHarness.App.ViewModels;

namespace TaskHarness.App;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        var vm = new MainViewModel
        {
            PickFolder = PickProjectDir
        };
        DataContext = vm;
        Loaded += (_, _) => vm.Boot();
    }

    string? PickProjectDir()
    {
        var dialog = new OpenFolderDialog
        {
            Title = "选择项目任务目录",
            Multiselect = false
        };
        if (DataContext is MainViewModel vm)
        {
            var start = vm.ProjectPath;
            if (!string.IsNullOrWhiteSpace(start) && start != "未选择目录" && Directory.Exists(start))
                dialog.InitialDirectory = start;
        }
        return dialog.ShowDialog(this) == true ? dialog.FolderName : null;
    }
}
