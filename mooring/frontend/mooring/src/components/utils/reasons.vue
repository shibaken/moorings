<template lang="html">
    <div class="row" id="reasons">
        <div class="form-group">
            <div v-bind:class="{'col-md-4':large, 'col-md-2': !large }">
                <label>Reason: </label>
            </div>
            <div v-bind:class="{'col-md-8':large,'col-md-4':!large, 'col-md-10':wide, 'col-md-9':threenine, 'col-md-4':!wide, }">
                <select v-if="!reasons.length > 0" class="form-control" >
                    <option value="">Loading...</option>
                </select>
                <select v-else name="open_reason" :value="value" @change="$emit('input', $event.target.value)" class="form-control">
                    <option value=""></option>
                    <option v-for="reason in reasons" :value="reason.id">{{reason.text}}</option>
                </select>
            </div>
        </div>
    </div>
</template>

<script>
import {
    $,
    api_endpoints,
    bus
}from '../../hooks.js'
export default {
    name:'reasons',
    data:function () {
        let vm =this;
        return {
            reasons:[]
        }
    },
    props:{
        type:{
            required:true
        },
        value:{

        },
        large:{
            default:function () {
                return false;
            }
        },
        wide: {
            default: function(){
                return false;
            }
        },
        threenine: {
            default: function() {
                return false;
            }
        }
    },
    methods:{
        fetchOpenReasons:function () {
            let vm = this;
            $.get(api_endpoints.openReasons(),function (data) {
                vm.reasons = data;
                bus.$emit('openReasons', vm.reasons);
            });
        },
        fetchClosureReasons:function () {
            let vm = this;
            $.get(api_endpoints.closureReasons(),function (data) {
                vm.reasons = data;
                bus.$emit('closeReasons', vm.reasons);
            });
        },
        fetchMaxStayReasons:function () {
            let vm = this;
            $.get(api_endpoints.maxStayReasons(),function (data) {
                vm.reasons = data;
                bus.$emit('maxStayReasons', vm.reasons);
            });
        },
        fetchPriceReasons:function () {
            let vm = this;
            $.get(api_endpoints.priceReasons(),function (data) {
                vm.reasons = data;
                bus.$emit('priceReasons', vm.reasons);
            });
        }
    },
    mounted:function(){
        let vm =this;
        if(vm.type){
            switch (vm.type.toLowerCase()) {
                case 'close':
                    vm.fetchClosureReasons();
                    break;
                case 'open':
                    vm.fetchOpenReasons();
                    break;
                case 'stay':
                    vm.fetchMaxStayReasons();
                    break;
                case 'price':
                    vm.fetchPriceReasons();
                    break;
            }
        }
    }
}
</script>

<style lang="css">
</style>
