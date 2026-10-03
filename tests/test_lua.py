from crapper.discover import is_test_file, language_of
from crapper.languages.lua import functions_in_source


def test_functions_methods_and_assigned_closures():
    source = """
local M = {}

function M.choose(x, ready)
  if x > 0 and x < 10 then
    return 1
  elseif x == 0 or ready then
    return 0
  end
  for i = 1, x do
    if i == 2 then return i end
  end
  for _, v in ipairs(ready) do
    while v do break end
  end
  repeat x = x - 1 until x <= 0
  goto done
  ::done::
  return x
end

function Account:deposit(amount)
  self.balance = self.balance + amount
end

local function helper(n)
  return n and n > 0 or false
end

local first, second = 1, function(s)
  if s then return s end
end

M.bar = function() return 1 end

function global_fn() end

return M
"""
    functions = functions_in_source(source, "src/demo/box.lua", "/proj")
    assert [(fn.namespace, fn.name, fn.complexity) for fn in functions] == [
        ("demo.box", "M.choose", 10),
        ("demo.box", "Account:deposit", 1),
        ("demo.box", "helper", 3),
        ("demo.box", "second", 2),
        ("demo.box", "M.bar", 1),
        ("demo.box", "global_fn", 1),
    ]


def test_nested_and_anonymous_functions_stay_inside_their_parent():
    source = """
local function outer(xs)
  local function inner(n)
    if n then return 1 end
    return 0
  end
  local pick = function(n) return n or 0 end
  table.sort(xs, function(a, b) return a < b and true end)
  return inner(1)
end

table.sort({}, function(a, b) if a then return true end end)

local t = { f = function() end }
"""
    functions = functions_in_source(source, "a.lua", "/proj")
    assert [(fn.name, fn.complexity) for fn in functions] == [("outer", 4)]


def test_local_function_expression_starts_at_local():
    source = "\nlocal f =\n  function()\n    return 1\n  end\n"
    [found] = functions_in_source(source, "a.lua", "/proj")
    assert (found.start_line, found.end_line) == (2, 5)


def test_namespace_strips_lua_roots_and_init():
    source = "function f() end\n"

    def namespace(path, root="/proj"):
        return functions_in_source(source, path, root)[0].namespace

    assert namespace("/proj/src/demo/app.lua") == "demo.app"
    assert namespace("./src/lua/demo/app.lua", ".") == "demo.app"
    assert namespace("lua/demo/init.lua") == "demo"
    assert namespace("demo/util/init.lua") == "demo.util"
    assert namespace("init.lua") == "init"
    assert namespace("vendor/src/x.lua") == "vendor.src.x"


def test_strings_and_comments_do_not_add_decisions():
    source = """
function literal()
  local text = "if x and y then"
  -- if x or y then
  --[[ while true do end ]]
  return text
end
"""
    [found] = functions_in_source(source, "a.lua", "/proj")
    assert found.complexity == 1


def test_lua_files_and_busted_specs_are_recognized():
    assert language_of("src/demo/app.lua") == "lua"
    assert is_test_file("src/demo/app_spec.lua")
    assert is_test_file("spec/app.lua")
    assert not is_test_file("src/demo/app.lua")
