clc; clear; close all;

%% add search path
toolbox_dir = fullfile('..', '..', '..', 'erinn');
addpath(genpath(toolbox_dir));

%% setting variables
prediction_dir = fullfile('..', 'models', 'predictions');
config_json = fullfile('..', 'config', 'config.json');
testing_h5 = fullfile(prediction_dir, 'testing.h5');
daily_h5 = fullfile(prediction_dir, 'daily.h5');
report_dir = fullfile('..', 'reports');

out_testing_dir = fullfile(report_dir, 'testing_figs');
if ~exist(out_testing_dir, 'dir')
    mkdir(out_testing_dir);
end

synth_data_testing = load_synth_data(testing_h5);
daily_data = load_daily_data(daily_h5);

%% synthetic data: crossplot(synth_V v.s. pred_V)
for i = 1:size(synth_data.synth_V, 1)
    fig = crossplot_synth(synth_data_testing.synth_V(i, :), ...
                          synth_data_testing.pred_V(i, :));
    
    img_name = fullfile(out_testing_dir, ...
                        strcat('crossplot_', num2str(i),'.png'));
    print(fig, img_name, '-dpng', '-r300');
    close(fig);
end

%% synthetic data: subsurface structureplot
nx = h5read(testing_h5, '/glob_para/nx');
nz = h5read(testing_h5, '/glob_para/nz');
coord = h5read(testing_h5, '/glob_para/coord_in_model');
xz = coord(:, [2, 4]) + [nx/2, 0];
min_log_rho = 0;
max_log_rho = 3;
log_rho_range = [min_log_rho, max_log_rho];
ticks = 0:0.5:3;
ticklabels = cellfun(@(x) num2str(x, '%.1f'), ...
                     num2cell(10 .^ ticks), ...
                     'UniformOutput', false);
for i = 1:size(synth_data.synth_log_rho, 1)
    synth_log_rho = reshape(synth_data_testing.synth_log_rho(i, :), nx, nz)';
    pred_log_rho = reshape(synth_data_testing.pred_log_rho(i, :), nx, nz)';
    fig = structureplot_synth(synth_log_rho, pred_log_rho, nx, nz, xz);
    ax1 = fig.Children.findobj('-regexp', 'Tag', 'ax1');
    cbar1 = fig.Children.findobj('-regexp', 'Tag', 'cbar1');
    ax2 = fig.Children.findobj('-regexp', 'Tag', 'ax2');
    cbar2 = fig.Children.findobj('-regexp', 'Tag', 'cbar2');
    caxis(ax1, log_rho_range);
    cbar1.Ticks = ticks;
    cbar1.TickLabels = ticklabels;
    caxis(ax2, log_rho_range);
    cbar2.Ticks = ticks;
    cbar2.TickLabels = ticklabels;
    
    img_name = fullfile(out_testing_dir, ...
                        strcat('structureplot_', num2str(i),'.png'));
    print(fig, img_name, '-dpng', '-r300');
    close(fig);
end

%% synthetic data: heatmap(synth_log_rho v.s. pred_log_rho)
fig = heatmap_synth(synth_data_testing.synth_log_rho, ...
                    synth_data_testing.pred_log_rho);
img_name = fullfile(out_testing_dir, 'heatmap.png');
print(fig, img_name, '-dpng', '-r300');
close(fig);

%% daily data: crossplot(obs_V v.s. pred_V)
for i = 1:size(daily_data.obs_V, 1)
    fig = crossplot_daily(daily_data.obs_V(i, :), ...
                          daily_data.pred_V(i, :));
    fig.CurrentAxes.Title.String = daily_data.date{i};
    img_name = fullfile(out_daily_dir,...
                        strcat('crossplot_', daily_data.date{i},'.png'));
    print(fig, img_name, '-dpng', '-r300');
    close(fig);
end

%% daily data: subsurface structureplot
for i = 1:size(daily_data.obs_V, 1)
    pred_log_rho = reshape(daily_data.pred_log_rho(i, :), nx, nz)';
    fig = structureplot_daily(pred_log_rho, nx, nz, xz);
    fig.CurrentAxes.Title.String = daily_data.date{i};
    cbar = fig.Children.findobj('-regexp', 'Tag', 'cbar');
    caxis(log_rho_range);
    cbar.Ticks = ticks;
    cbar.TickLabels = ticklabels;
    img_name = fullfile(out_daily_dir,...
                        strcat('structureplot_', daily_data.date{i},'.png'));
    print(fig, img_name, '-dpng', '-r300');
    close(fig);
end

%% remove search path
rmpath(genpath(toolbox_dir));
