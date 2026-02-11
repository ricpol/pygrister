# This is the standalone bundle of the Gry command line tool 
# for interacting with the Grist Api. 
# Use this Python module to add your type converter functions if needed.
# This is entirely optional: you may use Gry without declaring converters.
# See Gry/Pygrister docs for more details.
#
# 1) Write your converter functions here, like 
#
# def myconverter(val: str) -> int:
#     return int(val)
#
# 2) Register your converters in the 2 following dictionaries, like this:
#                        table ID    column ID   conv. function
#                        vvvvvvvv    vvvvvvvv    vvvvvvvvvvv
#
# cli_out_converters = {
#                        'table1': {
#                                   'columnA':   myconverter,
#                                  },
#                      }


# this is for converting "input" data, that you are about to write to Grist
cli_in_converters = {}

# this is for converting "output" data, that you are receiving from Grist
cli_out_converters = {}
