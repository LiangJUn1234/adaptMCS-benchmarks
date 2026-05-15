function out = mp_run_dcpf_minimal(case_data, debug, ac_fail_as_violation)
%MP_RUN_DCPF_MINIMAL Minimal DC PF wrapper with scalar score outputs.
%   out = MP_RUN_DCPF_MINIMAL(case_data, debug, ac_fail_as_violation)
%   accepts either a MATPOWER case name (e.g., 'case14') or case struct,
%   runs DC PF once, and returns scalar security scores.
%
%   Returned fields (default):
%   - success
%   - s_line
%   - s_volt
%   - s_any
%
%   Detailed arrays are only returned when debug=true.
%
%   TODO:
%   - Confirm final policy for solver-failure handling in DC path.
%   - Add explicit MATPOWER version/feature checks.

if nargin < 2 || isempty(debug)
    debug = false;
end
if nargin < 3 || isempty(ac_fail_as_violation)
    ac_fail_as_violation = true;
end

mpc = local_load_case(case_data);
mpopt = mpoption('verbose', 0, 'out.all', 0);

warning('off', 'MATLAB:rmpath:DirNotFound'); try, opt_path = fileparts(which('opt_model')); osqp_path = fullfile(opt_path, '.github', 'osqp'); if contains(path, osqp_path), rmpath(osqp_path); end, catch, end; warning('on', 'MATLAB:rmpath:DirNotFound');
[result, success] = rundcpf(mpc, mpopt);
out = local_finalize_output(result, success, debug, ac_fail_as_violation);
end

function mpc = local_load_case(case_data)
if ischar(case_data) || isstring(case_data)
    mpc = loadcase(char(case_data));
elseif isstruct(case_data)
    mpc = case_data;
else
    error('case_data must be MATPOWER case name or struct.');
end
end

function out = local_finalize_output(result, success, debug, fail_as_violation)
out = struct();
out.success = logical(success);

if ~success
    if fail_as_violation
        out.s_line = inf;
        out.s_volt = inf;
        out.s_any = inf;
    else
        out.s_line = -inf;
        out.s_volt = -inf;
        out.s_any = -inf;
    end
    if debug
        out.bus = result.bus;
        out.branch = result.branch;
    end
    return;
end

[s_line, s_volt, s_any] = local_compute_scores(result.bus, result.branch);
out.s_line = s_line;
out.s_volt = s_volt;
out.s_any = s_any;

if debug
    out.bus = result.bus;
    out.branch = result.branch;
end
end

function [s_line, s_volt, s_any] = local_compute_scores(bus, branch)
[PQ, PV, REF, NONE, BUS_I, BUS_TYPE, PD, QD, GS, BS, BUS_AREA, VM, ...
    VA, BASE_KV, ZONE, VMAX, VMIN] = idx_bus(); %#ok<ASGLU>
[F_BUS, T_BUS, BR_R, BR_X, BR_B, RATE_A, RATE_B, RATE_C, TAP, SHIFT, ...
    BR_STATUS, PF, QF, PT, QT, MU_SF, MU_ST, ANGMIN, ANGMAX, ...
    MU_ANGMIN, MU_ANGMAX] = idx_brch(); %#ok<ASGLU>

rate = branch(:, RATE_A);
status = branch(:, BR_STATUS);
eligible = (status == 1) & isfinite(rate) & (rate > 0);

if any(eligible)
    if size(branch, 2) >= QT
        from_loading = hypot(branch(:, PF), branch(:, QF));
        to_loading = hypot(branch(:, PT), branch(:, QT));
    else
        from_loading = abs(branch(:, PF));
        to_loading = abs(branch(:, PT));
    end
    loading = max(from_loading, to_loading);
    s_line = max(loading(eligible) - rate(eligible));
else
    s_line = -inf;
end

if size(bus, 2) >= VMIN
    vm = bus(:, VM);
    vmax = bus(:, VMAX);
    vmin = bus(:, VMIN);
    s_volt = max([vmin - vm; vm - vmax]);
else
    s_volt = -inf;
end

s_any = max(s_line, s_volt);
end
