function out = mp_eval_damaged_case_minimal(case_data, state_payload, mode, debug, ac_fail_as_violation)
%MP_EVAL_DAMAGED_CASE_MINIMAL Robust wrapper with crash protection.

if nargin < 4 || isempty(debug)
    debug = false;
end
if nargin < 5 || isempty(ac_fail_as_violation)
    ac_fail_as_violation = true;
end

% 1. 尝试注入损伤（如果 JSON 解析失败或拓扑构建崩溃，直接返回失败）
try
    mpc_damaged = mp_apply_damage_state_minimal(case_data, state_payload);
catch ME
    if debug, fprintf('Damage application failed: %s\n', ME.message); end
    out = local_make_failure_struct();
    return;
end

% 2. 带异常捕获的求解过程
mode = lower(char(mode));
try
    switch mode
        case 'acpf'
            out = mp_run_acpf_minimal(mpc_damaged, debug, ac_fail_as_violation);
        case 'acopf'
            out = mp_run_acopf_minimal(mpc_damaged, debug, ac_fail_as_violation);
        case 'dcpf'
            out = mp_run_dcpf_minimal(mpc_damaged, debug, ac_fail_as_violation);
        case 'fdxb'
            out = mp_run_fdxb_minimal(mpc_damaged, debug, ac_fail_as_violation);
        otherwise
            error('Unsupported damaged evaluation mode: %s', mode);
    end
catch ME
    % 捕获包括 'Index exceeds array bounds' 在内的所有求解器硬崩溃
    if debug
        fprintf('CRITICAL: Solver hard-crashed in mode %s\n', mode);
        fprintf('Error ID: %s\n', ME.identifier);
        fprintf('Error Message: %s\n', ME.message);
    end
    % 只要崩溃，就视为该状态极度危险（inf 违约）
    out = local_make_failure_struct();
end

end

function out = local_make_failure_struct()
    % 统一定义失败时的返回字典
    out = struct();
    out.success = logical(0);
    out.s_line = inf;
    out.s_volt = inf;
    out.s_any  = inf;
end
