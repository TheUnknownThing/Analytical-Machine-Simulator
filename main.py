from flask import Flask, render_template, request, jsonify
import re
import json

class AnalyticalMachineSimulator:
    def __init__(self):
        self.reset()
        
    def reset(self):
        """Reset the machine state"""
        # Memory layout:
        # 0: I1' (first ingress prime)
        # 1: I1 (first ingress)
        # 2: I2 (second ingress)
        # 3: E' (egress prime)
        # 4: E (egress)
        # 5-14: V0-V9 (variables)
        self.memory = [0] * 15
        self.mode = '~'  # Current operation mode, ~ for unset
        self.runup_lever = 0  # 0: unset, 1: set
        self.program_counter = 0
        self.max_steps = 1000
        self.steps = 0
        self.debug_info = []
        self.output = []
        
    def execute_program(self, program):
        """Execute a program (list of instructions)"""
        self.reset()
        self.program = []
        for line in program:
            stripped = line.split('#')[0].strip()
            if stripped:
                self.program.append(stripped)
        
        self.program_counter = 0
        self.steps = 0
        
        try:
            while self.program_counter < len(self.program) and self.steps < self.max_steps:
                print("Now at line", self.program_counter + 1)
                self.execute_instruction(self.program[self.program_counter])
                self.program_counter += 1
                self.steps += 1
                
            if self.steps >= self.max_steps:
                raise Exception("Program exceeded maximum step count")
                
            return {
                'debug_info': self.debug_info,
                'output': self.output,
                'final_memory': self.memory[:]
            }
        except Exception as e:
            raise Exception(f"Error at line {self.program_counter + 1}: {str(e)}")
            
    def execute_instruction(self, instruction):
        """Execute a single instruction"""
        parts = instruction.split()
        if not parts:
            return
            
        op = parts[0]

        changed_columns = []
        initial_values = self.memory.copy()
        
        try:
            if op in ['+', '-', '*', '/']:
                self.mode = op
                self.runup_lever = 0
            
            elif op == 'N':
                if len(parts) != 3:
                    raise Exception(f"Invalid N instruction format: {instruction}")
                k = int(parts[1])
                n = int(parts[2])
                if k < 0 or k > 9:
                    raise Exception(f"Invalid variable number: {k}")
                self.memory[k + 5] = n
                changed_columns.append((k + 5, n))
                
            elif op.startswith('L'):
                if self.mode == '~':
                    raise Exception("Cannot load before setting operation mode")
                if len(parts) != 2:
                    raise Exception(f"Invalid L instruction format: {instruction}")
                k = int(parts[1])
                if k < 0 or k > 9:
                    raise Exception(f"Invalid variable number: {k}")
                value = self.memory[k + 5]
                
                if "'" in op:
                    self.memory[0] = value
                    changed_columns.append((0, value))
                else:
                    if self.memory[1] == 0:
                        self.memory[1] = value  # Load to I1
                        changed_columns.append((1, value))
                    else:
                        self.memory[2] = value  # Load to I2
                        changed_columns.append((2, value))
                    
            elif op.startswith('S'):
                if len(parts) != 2:
                    raise Exception(f"Invalid S instruction format: {instruction}")
                k = int(parts[1])
                if k < 0 or k > 9:
                    raise Exception(f"Invalid variable number: {k}")
                source_index = 3 if "'" in op else 4  # E' is index 3, E is index 4
                value = self.memory[source_index]
                self.memory[k + 5] = value
                changed_columns.append((k + 5, value))
                
            elif op == 'P':
                if len(parts) != 2:
                    raise Exception(f"Invalid P instruction format: {instruction}")
                k = int(parts[1])
                print(self.memory[k + 5])
                if k < 0 or k > 9:
                    raise Exception(f"Invalid variable number: {k}")
                self.output.append(self.memory[k + 5])
                
            elif op in ['F', 'B']:
                if len(parts) != 2:
                    raise Exception(f"Invalid {op} instruction format: {instruction}")
                n = int(parts[1])
                if op == 'F':
                    self.program_counter += n
                else:
                    self.program_counter -= n
                    
            elif op in ['?F', '?B']:
                if len(parts) != 2:
                    raise Exception(f"Invalid {op} instruction format: {instruction}")
                if self.runup_lever:
                    n = int(parts[1])
                    if op == '?F':
                        self.program_counter += n
                    else:
                        self.program_counter -= n
            
            if self.mode in ['+', '-', '*', '/']:
                i1_prime, i1, i2 = self.memory[0], self.memory[1], self.memory[2]
                
                if self.mode == '+':
                    result = i1 + i2
                    self.memory[4] = result
                    if abs(result) > 99999:  # Assuming 5-digit limit
                        self.runup_lever = 1
                    changed_columns.append((4, result))
                    
                elif self.mode == '-':
                    result = i1 - i2
                    self.memory[4] = result
                    if result < 0:
                        self.runup_lever = 1
                    changed_columns.append((4, result))
                    
                elif self.mode == '*':
                    result = i1 * i2
                    self.memory[4] = result % 100000
                    self.memory[3] = result // 100000
                    changed_columns.append((4, self.memory[4]))
                    changed_columns.append((3, self.memory[3]))
                    
                elif self.mode == '/':
                    combined_dividend = i1_prime * 100000 + i1
                    if i2 == 0:
                        self.runup_lever = 1
                    else:
                        quotient = combined_dividend // i2
                        remainder = combined_dividend % i2
                        self.memory[3] = quotient
                        self.memory[4] = remainder
                        if quotient > 99999:
                            self.runup_lever = 1
                        changed_columns.append((3, quotient))
                        changed_columns.append((4, remainder))
            
            debug_step = {
                'step': self.steps + 1,
                'mode': self.mode,
                'runup': self.runup_lever,
                'line': self.program_counter + 1,
                'changes': changed_columns,
                'instruction': instruction,
                'memory': self.memory[:]
            }
            self.debug_info.append(debug_step)
            
        except ValueError as e:
            raise Exception(f"Invalid number format in instruction: {instruction}")
        except Exception as e:
            raise Exception(f"Error executing instruction '{instruction}': {str(e)}")

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run_program():
    try:
        data = request.get_json()
        if not data or 'code' not in data:
            return jsonify({
                'status': 'error',
                'message': 'No code provided'
            }), 400
            
        code = data['code']
        simulator = AnalyticalMachineSimulator()
        result = simulator.execute_program(code.split('\n'))
        
        return jsonify({
            'status': 'success',
            'result': result
        })
    except json.JSONDecodeError:
        return jsonify({
            'status': 'error',
            'message': 'Invalid JSON in request'
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0',port=9000)