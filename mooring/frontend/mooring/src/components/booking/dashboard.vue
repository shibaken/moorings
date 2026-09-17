<template lang="html" id="booking-dashboard">
    <div v-if="!isLoading">
        <div class="card">
            <div class="card-header" id="bookings-heading">
                <h2 class="mb-0">
                    <button 
                        class="btn d-flex justify-content-between align-items-center w-100 text-start text-decoration-none"
                        type="button"
                        :aria-expanded="isExpanded"
                        aria-controls="bookings-collapse"
                        @click="toggleCollapse"
                    >
                        <h3 class="mb-0">Bookings</h3>
                        <i :class="['bi', isExpanded ? 'bi-chevron-up' : 'bi-chevron-down', 'fs-4', 'fw-bold']"></i>
                    </button>
                </h2>
            </div>
            <div 
                id="bookings-collapse"
                class="collapse show"  
                aria-labelledby="bookings-heading"
                ref="collapseElement"
            >
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-12">
                            <button v-if="!exportingCSV" type="button" class="btn btn-primary pull-right" id="print-btn" @click="print()">
                                <i class="fa fa-file-excel-o" aria-hidden="true"></i> Export to CSV
                            </button>
                            <button v-else type="button" class="btn btn-primary pull-right" disabled>
                                <i class="fa fa-circle-o-notch fa-spin" aria-hidden="true"></i> Exporting to CSV
                            </button>
                        </div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-md-4">
                            <label for="" class="form-label">Mooring</label>
                            <select v-show="isLoading" class="form-control" >
                                <option value="">Loading...</option>
                            </select>
                            <select ref="campgroundSelector" v-if="!isLoading" class="form-control" v-model="filterCampground" id="filterCampground">
                                <option value="All">All</option>
                                <option v-for="campground in campgrounds" :value="campground.id">{{campground.name}}</option>
                            </select>
                        </div>
                        <div class="col-md-4">
                            <label for="" class="form-label">Region</label>
                            <select v-show="isLoading" class="form-control" name="">
                                <option value="">Loading...</option>
                            </select>
                            <select ref="regionSelector" v-if="!isLoading" class="form-control" v-model="filterRegion" id="filterRegion">
                                <option value="All">All</option>
                                <option v-for="region in regions" :value="region.id">{{region.name}}</option>
                            </select>
                        </div>
                        <div class="col-md-4">
                            <label for="" class="form-label">Cancelled</label>
                            <select class="form-control" v-model="filterCanceled" id="filterCanceled">
                                <option value="True">Yes</option>
                                <option value="False">No</option>
                            </select>
                        </div>
                    </div>
                    <div class="row" style="margin-bottom:10px;">
                        <div class="col-md-4">
                            <label for="booking-date-from" class="form-label">Date From</label>
                            <input
                                id="booking-date-from"
                                type="date"
                                class="form-control"
                                v-model="booking_date_from"
                                :max="booking_date_to"
                            >
                        </div>
                        <div class="col-md-4">
                            <label for="booking-date-to" class="form-label">Date To</label>
                            <input
                                id="booking-date-to"
                                type="date"
                                class="form-control"
                                v-model="booking_date_to"
                                :min="booking_date_from"
                            >
                        </div>
                        <div class="col-md-4">
                            <label for="BookingKeyword" class="form-label">Keyword</label>
                            <input type="text" class="form-control"  placeholder="" v-model="filterBookingKeyword" name='BookingKeyword' id="BookingKeyword">
                        </div>

                        <div style='display: none;' class="col-md-4" iv-if="filterCanceled == 'True'">
                            <div class="form-group">
                            <label for="">Refund Status</label>
                            <select class="form-control" v-model="filterRefundStatus" id="filterRefundStatus">
                                    <option value="All">All</option>
                                    <option value="Refunded">Refunded</option>
                                    <option value="Partially Refunded">Partially Refunded</option>
                                    <option value="Not Refunded">Not Refunded</option>
                            </select>
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-lg-12">
                            <datatable ref="bookings_table" id="bookings-table" :dtOptions="dtOptions" :dtHeaders="dtHeaders"></datatable>
                        </div>
                    </div>
                    before
                    <!-- <changebooking ref="changebooking" :booking_id="selected_booking" :campgrounds="campgrounds"/> -->
                    <bookingHistory ref="bookingHistory" :booking_id="selected_booking" />
                </div>
            </div>
        </div>
    </div>
    <div v-else>
        <loader :isLoading="isLoading">{{ loading.join(', ') }}</loader>
    </div>

    <div v-if="!isLoading2" class="mt-3">
        <div class="card">
            <div class="card-header" id="admissions-heading">
                <h2 class="mb-0">
                    <button 
                        class="btn d-flex justify-content-between align-items-center w-100 text-start text-decoration-none"
                        type="button"
                        :aria-expanded="isExpanded2"
                        aria-controls="admissions-collapse"
                        @click="toggleCollapse2"
                    >
                        <h3 class="mb-0">Admission Fee Payments</h3>
                        <i :class="['bi', isExpanded2 ? 'bi-chevron-up' : 'bi-chevron-down', 'fs-4', 'fw-bold']"></i>
                    </button>
                </h2>
            </div>
            <div 
                id="admissions-collapse"
                class="collapse show"  
                aria-labelledby="admissions-heading"
                ref="collapseElement2"
            >
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-12">
                            <button v-if="!exportingCSV2" type="button" class="btn btn-primary pull-right" id="print-btn" @click="print2()">
                                <i class="fa fa-file-excel-o" aria-hidden="true"></i> Export to CSV
                            </button>
                            <button v-else type="button" class="btn btn-primary pull-right" disabled>
                                <i class="fa fa-circle-o-notch fa-spin" aria-hidden="true"></i> Exporting to CSV
                            </button>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-3">
                            <label for="">Date From</label>
                            <input
                                type="date"
                                id="admission_date_from"
                                class="form-control"
                                placeholder="DD/MM/YYYY"
                                v-model="admission_date_from"
                                :max="admission_date_to"
                            >
                        </div>
                        <div class="col-md-3">
                            <label for="">Date To</label>
                            <input
                                type="date"
                                id="admission_date_to"
                                class="form-control"
                                placeholder="DD/MM/YYYY"
                                v-model="admission_date_to"
                                :min="admission_date_from"
                            >
                        </div>
                        <div class="col-md-3">
                            <div class="form-group">
                            <label for="">Cancelled</label>
                            <select class="form-control" v-model="filterCanceled2" id="filterCanceled2">
                                    <option value="True">Yes</option>
                                    <option value="False">No</option>
                            </select>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <label for="">Keyword</label>
                            <input type="text" class="form-control"  placeholder="" v-model="filterAdmissionKeyword" name='AdmissionKeyword' id="AdmissionKeyword">
                        </div>

                    </div>
                    <div class="row">
                        <div class="col-lg-12">
                            <datatable ref="admissions_table" id="admissions-bookings-table" :dtOptions="dtOptions2" :dtHeaders="dtHeaders2"></datatable>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div v-else>
        <loader :isLoading2="isLoading2">{{ loading2.join(', ') }}</loader>
    </div>
</template>


<script>
// Variabled ending with a 2 (except select2) are reused for the admissions fee payment table.
import { $, bus, api_endpoints, helpers, Moment, swal } from "../../hooks.js"
import loader from "../utils/loader.vue"
import datatable from '../utils/datatable.vue'
// import changebooking from "./changebooking.vue"
import bookingHistory from "./history.vue"
import modal from '../utils/bootstrap-modal.vue'
import { mapGetters } from 'vuex'
import { Parser } from '@json2csv/plainjs';

export default {
    name:'booking-dashboard',
    components:{
        datatable,
        loader,
        // changebooking,
        modal,
        bookingHistory
    },
    data:function () {
        let vm =this;
        return {
            exportingCSV: false,
            exportingCSV2: false,
            payment_officer: false,
            dtOptions:{
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: true,
                fnDrawCallback: function(oSettings, json){
                    if(vm.payment_officer){
                        vm.$refs.bookings_table.vmDataTable.rows().every(function(){
                            var rowdata = this.data();
                            rowdata['payment_visible'] = true;
                            this.data(rowdata);
                        });
                    }
                },
                serverSide:true,
                processing:true,
                searchDelay: 800,
                searching: false,
                ajax: {
                    "url": api_endpoints.bookings,
                    "dataSrc": 'results',
                    data :function (d) {
                        console.log('start');
                        if (vm.filterDateFromForBooking) {
                            d.arrival = vm.filterDateFromForBooking;
                        }
                        if (vm.filterDateToForBooking) {
                            d.departure = vm.filterDateToForBooking;
                        }
                        if (vm.filterCampground != "All") {
                            d.campground = vm.filterCampground;
                        }
                        if (vm.filterRegion != "All") {
                            d.region = vm.filterRegion;
                        }
                        d.canceled = vm.filterCanceled;
                        d.refund_status = vm.filterRefundStatus;
                        if (vm.filterBookingKeyword.length > 0) {
			     d.search_keyword = vm.filterBookingKeyword;
			}
                        console.log('end');
                        return d;
                    }
                },
                columnDefs: [
                    {
                        responsivePriority: 1,
                        targets: 0
                    },
                    {
                        responsivePriority: 2,
                        targets: 2
                    },
                    {
                        responsivePriority: 3,
                        targets: 7
                    }
                ],
                columns:[
                    {
                        data:"id",
                        orderable:false,
                        searchable:false,
                        mRender:function(data,type,full) {
                            return full.status != 'Canceled' ? "<a href='/api/get_confirmation/"+full.id+"' target='_blank' class='text-primary'>PS"+data+"</a><br/>": "PS"+full.id;
                        }
                    },
                    {
                        data: "firstname",
                        mRender: function(data, type, full) {
                            var name = full.firstname +" "+full.lastname;
                             var first_name = full.firstname ? full.firstname : '';
                             var last_name = full.lastname ? full.lastname : '';
                             var name = first_name +" "+ last_name;
                             var max_length = 25;
                             var short_name = (name.length > max_length) ? name.substring(0,max_length-1)+'...' : name;
                             var popover =  (name.length > max_length) ? "class=\"name_popover\"":"";
                             var column = '<td ><div '+popover+' tabindex="0" data-bs-toggle="popover" data-placement="top" data-bs-content="__NAME__">'+short_name+'</div>';

                             column += '<BR>'+ full.booking_phone_number;
                             column += '</td>';
                             column.replace(/__SHNAME__/g, short_name);
                             return column.replace(/__NAME__/g, name);
                        },
                        orderable:false,
                        searchable:false
                    },
                    {
                        data: "regos",
                        mRender: function(data, type, full){
                            if (full.regos.length > 0){
                                var rego = full.regos[0].vessel;
                            } else {
                                var rego = "-"
                            }
                            return rego;
                        },
                        orderable:false,
                        searchable:false
                    },
                    {
                        data: "mooringsite_bookings",
                        mRender: function(data, type, full){
                            var line = "<td>";
                            for (var msb in full.mooringsite_bookings){
                                line += '<tr>' + full.mooringsite_bookings[msb][0] + '<br/></tr>';
                            }
                            line += '</td>';
                            return line;
                        },
                        orderable: false,
                        searchable: false
                    },
                    {
                        data: "mooringsite_bookings",
                        mRender: function(data, type, full){
                            var line = '<td>';
                            for (var msb in full.mooringsite_bookings){
                                line += '<tr>' + full.mooringsite_bookings[msb][1] + '<br/></tr>';
                            }
                            line += '</td>';
                            return line;
                        },
                        orderable:false,
                        searchable:false
                    },
                    {
                        orderable:false,
                        searchable:false,
                        data: "mooringsite_bookings",
                        mRender:function(data,type,full){
                            var line = '<td>';
                            for (var msb in full.mooringsite_bookings){
                                var date = Moment(full.mooringsite_bookings[msb][2]).format('DD/MM/YYYY HH:mm');
                                line += '<tr>' + date + '<br/></tr>';
                            }
                            line += '</td>';
                            return line;
                        }
                    },
                    {
                        orderable:false,
                        searchable:false,
                        data: "mooringsite_bookings",
                        mRender:function(data,type,full){
                            var line = '<td>';
                            for (var msb in full.mooringsite_bookings){
                                var date = Moment(full.mooringsite_bookings[msb][3]).format('DD/MM/YYYY HH:mm');
                                line += '<tr>' + date + '<br/></tr>';
                            }
                            line += '</td>';
                            return line;
                        }
                    },
                    {
                        data:"invoice_status",
                        orderable:false,
                        searchable:false,
                        mRender: function(data,type,full){
                            if (data === 'Canceled' && full.cancellation_reason != null){
                                let val = helpers.dtPopover(full.cancellation_reason);
                                return `<span>${data}</span><br/><br/>${val}`;
                            }
                            return data;
                        },
                        'createdCell': helpers.dtPopoverCellFn
                    },
                    {
                        data: "mooringsite_bookings",
                        mRender: function(data, type, full) {
                            var status = (data == true) ? "Open" : "Temporarily Closed";
                            var booking = JSON.stringify(full);
                            var invoices = "";
                            var invoice = "/ledger/payments/invoice/"+full.invoice_reference;
                            var invoice_link= (full.invoice_reference)?"<a href='"+invoice+"' target='_blank' class='text-primary'>Invoice</a><br/>":"";
                            var column = "<td >";
                            if (full.invoices.length > 0) {
                                var invoice_string = '/ledger/payments/invoice/payment?';
                                $.each(full.invoices,function(i,n){
                                    invoice_string += 'invoice='+n+'&';
                                });
                                invoice_string = invoice_string.slice(0,-1);
                                var location_port = window.location.port ? ':'+window.location.port : '';
                                var location_url = `${window.location.protocol}//${window.location.hostname}${location_port}`;
                                invoice_string += full.payment_callback_url ? '&callback_url='+location_url+full.payment_callback_url : '';
//                                if (full.invoice_status == 'unpaid') { 
                               if(full.payment_visible){
                                     var payment = (full.invoice_status == 'paid') ? "View" : "Record";
                                
                                     var record_payment = "<a href='"+invoice_string+"' target='_blank' class='text-primary' data-rec-payment='' > "+payment+" Payment</a><br/>";
                                     column += record_payment; 
                                }                                
                            }
                            if (full.editable){
                                if (full.booking_type == 0 || full.booking_type == 1 || full.booking_type == 2) { 
                                var change_booking = "<a href='/view-booking/"+full.id+"' class='text-primary' > Change</a><br/>";
                                var cancel_booking = "<a href='/cancel-booking/"+full.id+"' class='text-primary' idata-cancel='"+booking+"' > Cancel</a><br/>";
                                column += cancel_booking;
                                column += change_booking;
			        }
                            }

                            full.has_history ? column += "<a href='/view-booking/"+full.id+"' class='text-primary' data-history = '"+booking+"' > View History</a><br/>" : '';
                            $.each(full.invoices,(i,v) =>{
                                invoices += "<a href='/mooring/payments/invoice-pdf/"+v+"' target='_blank' class='text-primary'><i style='color:red;' class='fa fa-file-pdf-o'></i>&nbsp #"+v+"</a><br/>"; 
                            });
                            invoices += " <a class='text-primary' href='/booking-history/"+full.id+"'>View History</a>";
                            column += invoices;
                            column += "</td>";
                            return column.replace('__Status__', status);
                        },
                        orderable:false,
                        searchable:false
                    },
                ]
            },
            dtOptions2:{
                language: {
                    processing: "<i class='fa fa-4x fa-spinner fa-spin'></i>"
                },
                responsive: true,
                fnDrawCallback: function(oSettings, json){
                    if(vm.payment_officer){
                        vm.$refs.admissions_table.vmDataTable.rows().every(function(){
                            var rowdata = this.data();
                            rowdata['payment_visible'] = true;
                            this.data(rowdata);
                        });
                    }
                },
                serverSide:true,
                processing:true,
                searchDelay: 800,
                searching:false,
                ajax: {
                    "url": api_endpoints.admissionsbookings,
                    "dataSrc": 'results',
                    data :function (d) {
                        if (vm.filterDateFromForAdmission) {
                            d.arrival = vm.filterDateFromForAdmission;
                        }
                        if (vm.filterDateToForAdmission) {
                            d.departure = vm.filterDateToForAdmission;
                        }
                        if (vm.filterAdmissionKeyword.length > 0) {
                             d.search_keyword = vm.filterAdmissionKeyword;
                        }
                        d.canceled = vm.filterCanceled2;
                    }
                },
                columns:[
                    {
                        data: "id",
                        mRender:function(data,type,full){
                            return "<a href='/api/get_admissions_confirmation/"+data+"' target='_blank' class='text-primary'>AD"+data+"</a><br/>";
                        },
                        orderable:false,
                        searchable:false
                    },
                    {
                        data: "booking", 
                        mRender: function(data, type, full){
                             if (full.booking){
                                return "<a href='/api/get_confirmation/"+full.booking+"' target='_blank' class='text-primary'>PS"+full.booking+"</a><br/>"
                            } else {
                                return "-"
                            }
                        },
                        orderable: false,
                        searchable: false,
                    },
                    {
                        data: "customerName",
                        orderable:false,
                        searchable:false
                    },
                    {
                        data: "mobile",
                        orderable:false,
                        searchable:false,
                        mRender: function(data, type, full){
                            if (full.mobile != null) { 
                                if (full.mobile.length > 0) {
                                    return full.mobile;
                                } else {
                                    return full.booking_phone;
                                }
                            } else {
                                return full.booking_phone;
                            }
                        },
                    },
                    {
                        data: "vesselRegNo",
                        mRender: function(data,type,full){
                            if(full.vesselRegNo){
                                return full.vesselRegNo;
                            } else {
                                return "-";
                            }
                        },
                        orderable:false,
                        searchable:false
                    },
                    {
                        data: "noOfAdults",
                        mRender:function(data,type,full){
                            return full.noOfAdults + full.noOfChildren + full.noOfInfants;
                        },
                        orderable:false,
                        searchable:false
                    },
                    {
                        data:"lines",
                        orderable:false,
                        searchable:false,
                        mRender:function(data,type,full){
                            var dates = ""
                            for (var no in full.lines){
                                dates += Moment(full.lines[no].date).format("DD/MM/YYYY") + "<br/>";
                            }
                            return dates;
                        }
                    },
                    {
                         data: "warningReferenceNo",
                         mRender: function(data,type,full){
                            if(full.warningReferenceNo){
                                return full.warningReferenceNo;
                            } else {
                                return "-";
                            }
                        },
                        orderable:false,
                        searchable:false
                    },
                    {
                        data: "invoice_ref",
                        mRender: function(data, type, full) {
                            var search = "";
                            var invoices = "";
                            var column = ""
                            $.each(full.invoice_ref,(i,v) =>{
                                if (i != 0){
                                    search += "&";
                                }
                                search += "invoice=" + v
                                invoices += "<a href='/mooring/payments/invoice-pdf/"+v+"' target='_blank' class='text-primary'><i style='color:red;' class='fa fa-file-pdf-o'></i>&nbsp #"+v+"</a><br/>"; 
                            });
                            var invoice = "/ledger/payments/invoice/payment?" + search;
                            if (full.payment_visible) {
                                var invoice_link= (full.invoice_ref)?"<a href='"+invoice+"' target='_blank' class='text-primary'>View Payment</a><br/>":"";
                                column += invoice_link;
                            }
                            if (full.in_future && !full.part_booking) {
                                if (full.booking_type == 0 || full.booking_type == 1 || full.booking_type == 2) { 
                                    var cancel_booking = "<a href='/cancel-admissions-booking/"+full.id+"' class='text-primary'> Cancel</a><br/>";
                                    column += cancel_booking;
                                }
                            }
                            // invoices += " <a href='/booking-history/{{ full.id }}'>View History</a>";
                            column += invoices;
                            return column;
                        },
                        orderable:false,
                        searchable:false
                    },
                ]
            },
            dtHeaders:["Confirmation #", "Person", "Vessel Reg #", "Mooring", "Region", "From", "To", "Status", "Action"],
            dtHeaders2:["Confirmation #", "Booking #", "Person","Mobile", "Vessel Reg #", "Total Attendees", "Admission Date", "Warning Ref #", "Action"],
            loading:[],
            loading2:[],
            selected_booking:-1,
            filterCampground:"All",
            filterRegion:"All",
            booking_date_from: '',  // Bind to <input type="date">, so the format is 'YYYY-MM-DD'
            booking_date_to: '',  // Bind to <input type="date">, so the format is 'YYYY-MM-DD'
            filterCanceled: 'False',
            filterRefundStatus: 'All',
            admission_date_from: '',  // Bind to <input type="date">, so the format is 'YYYY-MM-DD'
            admission_date_to: '',  // Bind to <input type="date">, so the format is 'YYYY-MM-DD'
            filterCanceled2: 'False',
            filterBookingKeyword: '',
            filterAdmissionKeyword: '',

            isExpanded: true,
            isExpanded2: true,
            collapseInstance: null,
            collapseInstance2: null,

        }
    },
    watch:{
        // Watchers to prevent invalid date ranges, especially from manual input.
        booking_date_from(newStartDate) {
            if (newStartDate && this.booking_date_to && newStartDate > this.booking_date_to) {
                this.booking_date_to = '';
            }
        },
        // Watchers to prevent invalid date ranges, especially from manual input.
        booking_date_to(newEndDate) {
            if (newEndDate && this.booking_date_from && newEndDate < this.booking_date_from) {
                this.booking_date_from = '';
            }
        },
        dateRangeIdentifierForReloadBookingTable() {
            this.reloadBookingTable();
        },
        // Watchers to prevent invalid date ranges, especially from manual input.
        admission_date_from(newStartDate) {
            if (newStartDate && this.admission_date_to && newStartDate > this.admission_date_to) {
                this.admission_date_to = '';
            }
        },
        // Watchers to prevent invalid date ranges, especially from manual input.
        admission_date_to(newEndDate) {
            if (newEndDate && this.admission_date_from && newEndDate < this.admission_date_from) {
                this.admission_date_from = '';
            }
        },
        dateRangeIdentifierForReloadAdmissionTable() {
            this.reloadAdmissionTable();
        },
        filterCampground: function() {
            this.reloadBookingTable()
        },
        filterRegion: function() {
            this.reloadBookingTable()
        },
        filterCanceled: function() {
            this.reloadBookingTable()
        },
        filterRefundStatus: function() {
            this.reloadBookingTable()
        },
    },
    computed:{
        filterDateFromForBooking: {
            get() {
                // If our internal date exists, convert it for submission, etc
                if (this.booking_date_from) {
                    return Moment(this.booking_date_from, 'YYYY-MM-DD').format('DD/MM/YYYY');
                }
                return ''; // Otherwise, return an empty string.
            }
        },
        filterDateToForBooking: {
            // GET:
            get() {
                if (this.booking_date_to) {
                    return Moment(this.booking_date_to, 'YYYY-MM-DD').format('DD/MM/YYYY');
                }
                return '';
            },
        },
        filterDateFromForAdmission: {
            get() {
                // If our internal date exists, convert it for submission, etc
                if (this.admission_date_from) {
                    return Moment(this.admission_date_from, 'YYYY-MM-DD').format('DD/MM/YYYY');
                }
                return ''; // Otherwise, return an empty string.
            }
        },
        filterDateToForAdmission: {
            // GET:
            get() {
                if (this.admission_date_to) {
                    return Moment(this.admission_date_to, 'YYYY-MM-DD').format('DD/MM/YYYY');
                }
                return '';
            },
        },
        // --- This is the NEW computed property for triggering the reload ---
        dateRangeIdentifierForReloadBookingTable() {
            return `${this.booking_date_from}|${this.booking_date_to}`;
        },
        dateRangeIdentifierForReloadAdmissionTable() {
            return `${this.admission_date_from}|${this.admission_date_to}`;
        },
        isLoading:function () {
            return this.loading.length > 0;
        },
        isLoading2: function (){
            return this.loading2.length > 0;
        },
        ...mapGetters([
          'regions',
          'campgrounds'
        ]),
    },
    methods:{
        reloadBookingTable() {
            if (this.$refs.bookings_table && this.$refs.bookings_table.vmDataTable) {
                this.$refs.bookings_table.vmDataTable.ajax.reload();
            } else {
                console.warn('Attempted to reload DataTable, but it was not available.');
            }
        },
        reloadAdmissionTable() {
            if (this.$refs.admissions_table && this.$refs.admissions_table.vmDataTable) {
                this.$refs.admissions_table.vmDataTable.ajax.reload();
            } else {
                console.warn('Attempted to reload DataTable, but it was not available.');
            }
        },
        showhidebookings: function() {
            var content = $('#content_booking');
            var span = $('#collapse_bookings_span');
            if (content.css("display") !== "none"){
                content.css("display", "none");
                span.removeClass("glyphicon glyphicon-menu-up");
                span.addClass("glyphicon glyphicon-menu-down");
            } else {
                content.css("display", "block");
                span.removeClass("glyphicon glyphicon-menu-down");
                span.addClass("glyphicon glyphicon-menu-up");
            }
        },
        showhideadmissions: function(){
            var content = $('#content_admissions')
            var span = $('#collapse_admissions_span');
            if (content.css("display") !== "none"){
                content.css("display", "none");
                span.removeClass("glyphicon glyphicon-menu-up");
                span.addClass("glyphicon glyphicon-menu-down");
            } else {
                content.css("display", "block");
                span.removeClass("glyphicon glyphicon-menu-down");
                span.addClass("glyphicon glyphicon-menu-up");
            }
        },
        fetchCampgrounds:function () {
            let vm =this;
            vm.loading.push('fetching campgrounds');
            if (vm.campgrounds.length == 0) {
                vm.$store.dispatch("fetchCampgrounds");
            }
            vm.loading.splice('fetching campgrounds',1);
        },
        fetchRegions:function () {
            let vm =this;
            if (vm.regions.length == 0) {
                vm.$store.dispatch("fetchRegions");
            }
        },
        cancelBooking:function (booking) {
            let vm =this;
            vm.$http.delete(api_endpoints.booking(booking.id),{
                emulateJSON:true,
                headers: {'X-CSRFToken': helpers.getCookie('csrftoken')}
            }).then((response)=>{
                vm.reloadBookingTable()
            },(error) =>{
                console.log(error);
            });
        },
        addEventListeners:function () {
            let vm =this;

            /* View History */
            vm.$refs.bookings_table.vmDataTable.on('click','a[data-history]',function (e) {
                e.preventDefault();
                var selected_booking = JSON.parse($(this).attr('data-history'));
                vm.selected_booking = selected_booking.id;
                vm.$refs.bookingHistory.booking = selected_booking;
                vm.$refs.bookingHistory.isModalOpen = true;

                //vm.$refs.changebooking.fetchBooking(vm.selected_booking);
            });

            /* Campground Selector*/
            $(vm.$refs.campgroundSelector).select2({
                "theme": "bootstrap-5",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.filterCampground = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.filterCampground = "All";
            }); 
            /* End Campground Selector*/

            /* Region Selector*/
            $(vm.$refs.regionSelector).select2({
                "theme": "bootstrap-5",
            }).
            on("select2:select",function (e) {
                var selected = $(e.currentTarget);
                vm.filterRegion = selected.val();
            }).
            on("select2:unselect",function (e) {
                var selected = $(e.currentTarget);
                vm.filterRegion = "All";
            }); 
            /* End Region Selector*/
            
            vm.$refs.bookings_table.vmDataTable.on('click','a[data-change]',function (e) {
                //e.preventDefault();
                //var selected_booking = JSON.parse($(this).attr('data-change'));
                //vm.selected_booking = selected_booking.id;
               // vm.$router.push({
               //     'name':'edit-booking',
                //    params: {
                //        booking_id: selected_booking.id
                //    }
               // })
                //vm.$refs.changebooking.fetchBooking(vm.selected_booking);
            });

            vm.$refs.bookings_table.vmDataTable.on('click','a[data-cancel]',function (e) {
                vm.selected_booking = JSON.parse($(this).attr('data-cancel'));
                swal.fire({
                  title: 'Cancel Booking',
                  text: "Provide a cancellation reason",
                  type: 'warning',
                  input: 'textarea',
                  showCancelButton: true,
                  confirmButtonText: 'Submit',
                  showLoaderOnConfirm: true,
                  preConfirm: function (reason) {
                    return new Promise(function (resolve, reject) {
                        vm.$http.delete(api_endpoints.booking(vm.selected_booking.id)+'?reason='+reason,{
                            emulateJSON:true,
                            headers: {'X-CSRFToken': helpers.getCookie('csrftoken')}
                        }).then((response)=>{
                            resolve()
                        },(error) =>{
                            reject(helpers.apiVueResourceError(error));
                        });
                    })
                  },
                  allowOutsideClick: false
                }).then(function (reason) {
                    vm.reloadBookingTable()
                    swal.fire({
                        type: 'success',
                        title: 'Booking Cancelled',
                        html: 'Booking PS' + vm.selected_booking.id + ' has been cancelled'
                    })
                })
                //bus.$emit('showAlert', 'cancelBooking');
                bus.emit('showAlert', 'cancelBooking');
            });
            $('#filterCanceled2').on('change',function (e) {
                   vm.reloadAdmissionTable();
	    });
            helpers.namePopover($,vm.$refs.bookings_table.vmDataTable);
            $(document).on('keydown', function(e) {
                if(e.ctrlKey && (e.key == "p" || e.charCode == 16 || e.charCode == 112 || e.keyCode == 80) ){
                    e.preventDefault();
                    bus.emit('showAlert', 'printBooking');
                    e.stopImmediatePropagation();
                }
            });
        },
        printParams() {
            let vm = this;
            var str = [];
            let obj = {
                arrival : vm.filterDateFromForBooking != null ? vm.filterDateFromForBooking: '',
                departure : vm.filterDateToForBooking != null ? vm.filterDateToForBooking:'' ,
                campground : vm.filterCampground != 'All' ? vm.filterCampground : '',
                region : vm.filterRegion != 'All' ? vm.filterRegion : '',
                canceled: vm.filterCanceled,
                length: 'all',
            }
             // 'search[value]': vm.$refs.bookings_table.vmDataTable.search()

            for(var p in obj)
                if (obj.hasOwnProperty(p)) {
                str.push(encodeURIComponent(p) + "=" + encodeURIComponent(obj[p]));
                }
            return str.join("&");
        },
        printParams2() {
            let vm = this;
            var str = [];
            let obj = {
                arrival : vm.filterDateFromForAdmission != null ? vm.filterDateFromForAdmission: '',
                departure : vm.filterDateToForAdmission != null ? vm.filterDateToForAdmission:'' ,
                'search[value]': vm.$refs.admissions_table.vmDataTable.search(),
                canceled: vm.filterCanceled2,
                length: 'all',
            }

            for(var p in obj)
                if (obj.hasOwnProperty(p)) {
                str.push(encodeURIComponent(p) + "=" + encodeURIComponent(obj[p]));
                }
            return str.join("&");
        },
        print: async function(){
            console.log('print()');
            let vm =this;
            vm.exportingCSV = true;
            
            let url = api_endpoints.bookings+'?'+vm.printParams();
            try {
                const response = await fetch(url);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();

                console.log({data})

                var fields = ['Created']
                var fields = [...fields,...vm.dtHeaders];
                fields.splice(vm.dtHeaders.length-1,1);
                fields = [
                    'Created',
                    'Confirmation No',
                    'Person',
                    'Email',
                    'Phone',

                    'Vessel Rego',
                    'Amount Due',
                    'Amount Paid',
                    "Status",
                    "Mooring",

                    "Region",
                    "Arrival",
                    "Departure",
                    "Adults",
                    "Concession",

                    "Children",
                    "Infants",
                    'Booking Type',
                    'Invoices',
                    'Admission Ref#',

                    'Admission Amount',
                    'Vessel Size',
                    'Vessel Draft',
                    'Vessel Beam',
                    'Vessel Weight',

                    'Cancelled By',
                    'Cancellation Reason'
                ];
                var booking_types = {
                    0: 'Reception booking',
                    1: 'Internet booking',
                    2: 'Black booking',
                    3: 'Temporary reservation',
                    4: 'Cancelled Booking',
                    5: 'Changed Booking',
                };

                var bookings = [];
                console.log('before $each')
                $.each(data.results,function (i, booking) {
                    var bk = {};
                    $.each(fields, function(j, field){
                        switch (j) {
                            case 0:
                                bk[field] = booking.created_date;
                                break;
                            case 1:
                                bk[field] = "PS" + booking.id;
                                break;
                            case 2:
                                bk[field] = booking.firstname +" "+ booking.lastname;
                                break;
                            case 3:
                                bk[field] = booking.email;
                                break;
                            case 4:
                                bk[field] = booking.booking_phone_number;
                                break;
                            case 5:
                                bk[field] = booking.regos?.[0]?.vessel ?? '';
                                break;
                            case 6:
                                bk[field] = booking.cost_total;
                                break;
                            case 7:
                                bk[field] = booking.amount_paid;
                                break;
                            case 8:
                                bk[field] = booking.invoice_status;
                                break;
                            case 9:
                                var name_list = []
                                console.log('9')
                                // for (var i = 0; i < booking.mooringsite_bookings.length; i++){
                                //     name_list.push(booking.mooringsite_bookings[i][0]);
                                // }
                                if (Array.isArray(booking.mooringsite_bookings)) {
                                    for (let i = 0; i < booking.mooringsite_bookings.length; i++) {
                                        if (Array.isArray(booking.mooringsite_bookings[i])) {
                                            name_list.push(booking.mooringsite_bookings[i][0]);
                                        }
                                    }
                                }
                                bk[field] = name_list;
                                break;
                            case 10:
                                console.log('10')
                                // var name_list = []
                                // for (var i = 0; i < booking.mooringsite_bookings.length; i++){
                                //     name_list.push(booking.mooringsite_bookings[i][1]);
                                // }
                                var name_list = booking.mooringsite_bookings?.map(item => item[1]) ?? [];
                                bk[field] = name_list;
                                break;
                            case 11:
                                // var name_list = []
                                console.log('11')
                                // for (var i = 0; i < booking.mooringsite_bookings.length; i++){
                                //     name_list.push(Moment(booking.mooringsite_bookings[i][2]).format('DD/MM/YYYY HH:mm'));
                                // }
                                var name_list = booking.mooringsite_bookings?.map(item => {
                                    return item && item[2] ? Moment(item[2]).format('DD/MM/YYYY HH:mm') : '';
                                }) ?? [];
                                bk[field] = name_list;
                                break;
                            case 12:
                                // var name_list = []
                                console.log('12')
                                // for (var i = 0; i < booking.mooringsite_bookings.length; i++){
                                //     for (var i = 0; i < booking.mooringsite_bookings.length; i++){
                                //         name_list.push(Moment(booking.mooringsite_bookings[i][3]).format('DD/MM/YYYY HH:mm'));
                                //     }
                                // }
                                var name_list = booking.mooringsite_bookings?.map(item => {
                                    return item && item[3] ? Moment(item[3]).format('DD/MM/YYYY HH:mm') : '';
                                }) ?? [];
                                bk[field] = name_list;
                                break;
                            case 13:
                                // bk[field] = booking.guests.adults;
                                console.log('13')
                                bk[field] = booking.guests?.adults ?? 0;
                                break;
                            case 14:
                                // bk[field] =  booking.guests.concession;
                                console.log('14')
                                bk[field] =  booking.guests?.concession ?? 0;
                                break;
                            case 15:
                                // bk[field] =  booking.guests.children;
                                console.log('15')
                                bk[field] =  booking.guests?.children ?? 0;
                                break;
                            case 16:
                                // bk[field] =  booking.guests.infants;
                                console.log('16')
                                bk[field] =  booking.guests?.infants ?? 0;
                                break;
                            case 17:
                                console.log('17')
                                if (typeof booking_types[booking.booking_type] !== 'undefined') {
                                    bk[field] = booking_types[booking.booking_type];
                                } else {
                                    bk[field] = booking.booking_type;
                                }
                                break;
                            case 18:
                                console.log('18')
                                bk[field] = booking.invoices;
                                break;
                            case 19:
                                console.log('19')
                                if (booking.admissions) { 
                                	bk[field] = 'AD' + booking.admissions.id;
                                } else {
                                    bk[field] = '';
                                }
                                break;
                            case 20:
                                console.log('20')
                                if (booking.admissions) {
                                    bk[field] = booking.admissions.amount;
                                } else {
                                    bk[field] = '';
                                }
                                break;
                            case 21:
                                console.log('21')
                                if (booking.vessel_details) {
                                        bk[field] = booking.vessel_details.vessel_size;
                                } else {
                                        bk[field] = '';
                                }
                                break;
                            case 22:
                                console.log('22')
                                if (booking.vessel_details) {
                                        bk[field] = booking.vessel_details.vessel_draft;
                                } else {
                                        bk[field] = '';
                                }
                                break;
                            case 23:
                                console.log('23')
                                if (booking.vessel_details) {
                                    bk[field] = booking.vessel_details.vessel_beam;
                                } else {
                                    bk[field] = '';
                                }
                                break;
                            case 24:
                                console.log('24')
                                if (booking.vessel_details) {
                                    bk[field] = booking.vessel_details.vessel_weight;
                                } else {
                                    bk[field] = '';
                                }
                                break;
                            case 25:
                                console.log('25')
                                bk[field] = booking.canceled_by;
                                break;
                            case 26:
                                console.log('26')
                                bk[field] = booking.cancelation_reason;
                                break;
                        }
                    });
                    bookings.push(bk);
                });
                console.log('after $each')
                // var csv = json2csv({ data:bookings, fields: fields });
                // var a = document.createElement("a"),
                // file = new Blob([csv], {type: 'text/csv'});

                // 1. Create an options object for the parser.
                const opts = { fields: fields };

                // 2. Instantiate the Parser with the options.
                const parser = new Parser(opts);
                console.log({parser})

                // 3. Call the .parse() method on the instance to convert your data.
                //    This replaces the old json2csv() function call.
                const csv = parser.parse(bookings);
                console.log({csv})

                // 4. Create a link element for downloading.
                var a = document.createElement("a");
                console.log({a})

                // 5. Create a Blob from the generated CSV string.
                let file = new Blob([csv], { type: 'text/csv' });
                console.log({file})

                var filterCampground = (vm.filterCampground == 'All') ? "All Moorings " : $('#filterCampground')[0].selectedOptions[0].text;
                var filterRegion = (vm.filterCampground == 'All') ? (vm.filterRegion == 'All')? "All Regions" : $('#filterRegion')[0].selectedOptions[0].text : "";
                var filterDates = (vm.filterDateFromForBooking) ? (vm.filterDateToForBooking) ? "From "+vm.filterDateFromForBooking + " To "+vm.filterDateToForBooking: "From "+vm.filterDateFromForBooking : (vm.filterDateToForBooking) ? " To "+vm.filterDateToForBooking : "" ;
                var filename =  filterCampground +  "_" + filterRegion + "_" +filterDates+ ".csv";
                if (window.navigator.msSaveOrOpenBlob){
                    console.log('IE10+ detected');
                    window.navigator.msSaveOrOpenBlob(file, filename);
                } // IE10+
                else { // Others
                    console.log('Non-IE10+ detected');
                    var create_url = URL.createObjectURL(file);
                    a.href = create_url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    setTimeout(function() {
                        document.body.removeChild(a);
                        window.URL.revokeObjectURL(url);
                    }, 0);
                }
                vm.exportingCSV = false;
            } catch (error) {
                vm.exportingCSV = false;
                swal.fire({
                    type: 'error',
                    title: 'Export Error', 
                    text: helpers.apiVueResourceError(error), 
                })
            }
        },
        print2: async function(){
            console.log('print2()');

            let vm =this;
            vm.exportingCSV2 = true;
            
            let url = api_endpoints.admissionsbookings+'?'+vm.printParams2();
            console.log(url);
            try {
                const response = await fetch(url);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();

                console.log({data})

                var fields = [
                    "Confirmation No",
                    "Customer",
                    "Email",
                    "Mobile",
                    "Overnight Stay",
                    "Arrival Date",
                    "Total Attendees",
                    "Adults",
                    "Children",
                    "Infants",
                    "Vessel Reg No",
                    "Warning Reference",
                    "Invoice Reference",
                    'Cancelled By',
                    'Cancellation Reason'
                ]

                var bookings = [];
                $.each(data.results, function(i, booking) {
                    var bk = {};
                    $.each(fields,function (j, field) {
                        switch (j) {
                            case 0:
                                bk[field] = "AD" + booking.id;
                                break;
                            case 1:
                                bk[field] = booking.customerName;
                                break;
                            case 2:
                                bk[field] = booking.email;
                                break;
                            case 3: 
                                 bk[field] = booking.mobile;
                                 break;
                            case 4:
                                var answer = "";
                                if(booking.lines){
                                    for (var line in booking.lines){
                                        if (line > 0){
                                            answer += ", ";
                                        }
                                        if (booking.lines[line].overnight){
                                            answer += "Yes";
                                        } else {
                                            answer += "No"
                                        }
                                    }
                                }
                                bk[field] = answer;
                                break;
                            case 5:
                                var dates = ""
                                if (booking.lines){
                                    for (var line in booking.lines){
                                        if (line > 0){
                                            dates += ", ";
                                        }
                                        dates += Moment(booking.lines[line].date).format("DD/MM/YYYY");
                                    }
                                }
                                bk[field] = dates
                                break;
                            case 6:
                                bk[field] = booking.noOfAdults + booking.noOfChildren + booking.noOfInfants;
                                break;
                            case 7:
                                bk[field] = booking.noOfAdults;
                                break;
                            case 8:
                                bk[field] = booking.noOfChildren;
                                break;
                            case 9:
                                bk[field] = booking.noOfInfants;
                                break;
                            case 10:
                                bk[field] = booking.vesselRegNo;
                                break;
                            case 11:
                                bk[field] = booking.warningReferenceNo;
                                break;
                            case 12:
                                bk[field] = booking.invoice_ref;
                                break;
                            case 13:
                                bk[field] = booking.canceled_by;
                                break;
                            case 14:
                                bk[field] = booking.cancellation_reason;
                                break;
                        }
                    });
                    bookings.push(bk);
                });
                // var csv = json2csv({ data:bookings, fields: fields });
                // var a = document.createElement("a"),
                // file = new Blob([csv], {type: 'text/csv'});

                // 1. Create an options object for the parser.
                const opts = { fields: fields };

                // 2. Instantiate the Parser with the options.
                const parser = new Parser(opts);

                // 3. Call the .parse() method on the instance to convert your data.
                //    This replaces the old json2csv() function call.
                const csv = parser.parse(bookings);

                // 4. Create a link element for downloading.
                var a = document.createElement("a");

                // 5. Create a Blob from the generated CSV string.
                let file = new Blob([csv], { type: 'text/csv' });
                var filterDates = (vm.filterDateFromForAdmission) ? (vm.filterDateToForAdmission) ? "From "+vm.filterDateFromForAdmission + " To "+vm.filterDateToForAdmission: "From "+vm.filterDateFromForAdmission : (vm.filterDateToForAdmission) ? " To "+vm.filterDateToForAdmission : "" ;
                var filename =  filterDates + "_admissions" + ".csv";
                filename.replace(" ", "_");
                if (window.navigator.msSaveOrOpenBlob) // IE10+
                    window.navigator.msSaveOrOpenBlob(file, filename);
                else { // Others
                    var create_url = URL.createObjectURL(file);
                    a.href = create_url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    setTimeout(function() {
                        document.body.removeChild(a);
                        window.URL.revokeObjectURL(url);
                    }, 0);
                }
                vm.exportingCSV2 = false;
            } catch (error) {
                vm.exportingCSV2 = false;
                swal.fire({
                    type: 'error',
                    title: 'Export Error', 
                    text: helpers.apiVueResourceError(error), 
                })
            }
        },
        toggleCollapse: function() {
            console.log('toggleCollapse()')
            if (this.collapseInstance) {
                console.log('Toggling collapse instance');
                this.collapseInstance.toggle();
            }
        },
        toggleCollapse2: function() {
            console.log('toggleCollapse2()')
            if (this.collapseInstance2) {
                console.log('Toggling collapse instance2');
                this.collapseInstance2.toggle();
            }
        }
    },
    created: function(){
        let vm = this;
        $.ajax({
            url: api_endpoints.profile,
            method: 'GET',
            dataType: 'json',
            success: function(data, stat, xhr){
                if(data.is_payment_officer){
                    vm.payment_officer = true;
                }
            }
        });
    },
    mounted:function () {
        let vm = this;

        const collapseEl = vm.$refs.collapseElement;
        if (collapseEl) {
            vm.collapseInstance = new bootstrap.Collapse(collapseEl, {
                toggle: false
            });
        }
        collapseEl.addEventListener('show.bs.collapse', () => {
            vm.isExpanded = true;
        });
        collapseEl.addEventListener('hide.bs.collapse', () => {
            vm.isExpanded = false;
        });
        
        const collapseEl2 = vm.$refs.collapseElement2;
        if (collapseEl2) {
            vm.collapseInstance2 = new bootstrap.Collapse(collapseEl2, {
                toggle: false
            });
        }
        collapseEl2.addEventListener('show.bs.collapse', () => {
            vm.isExpanded2 = true;
        });
        collapseEl2.addEventListener('hide.bs.collapse', () => {
            vm.isExpanded2 = false;
        });

        vm.fetchCampgrounds();
        vm.fetchRegions();
        vm.addEventListeners();
        //Bookings
        $('#bookings-collapse').on('shown.bs.collapse', function(){
            $('#collapse_bookings_span').removeClass("glyphicon glyphicon-menu-down");
            $('#collapse_bookings_span').addClass("glyphicon glyphicon-menu-up");

        });
        $('#bookings-collapse').on('hidden.bs.collapse', function(){
            $('#collapse_bookings_span').removeClass("glyphicon glyphicon-menu-up");
            $('#collapse_bookings_span').addClass("glyphicon glyphicon-menu-down");
        });
        //Admissions
        $('#admissions-collapse').on('shown.bs.collapse', function(){
            $('#collapse_admissions_span').removeClass("glyphicon glyphicon-menu-down");
            $('#collapse_admissions_span').addClass("glyphicon glyphicon-menu-up");

        });
        $('#admissions-collapse').on('hidden.bs.collapse', function(){
            $('#collapse_admissions_span').removeClass("glyphicon glyphicon-menu-up");
            $('#collapse_admissions_span').addClass("glyphicon glyphicon-menu-down");
        });

        $('#BookingKeyword').on('change', function() {
            vm.reloadBookingTable();
        });

        $('#AdmissionKeyword').on('change', function() { 
            vm.reloadAdmissionTable();
        }); 
    }
}
</script>

<style lang="css">
    .text-warning{
        color:#f0ad4e;
    }
    @media print {
        .col-md-3 {
            width: 25%;
            float:left;
        }

        a[href]:after {
           content: none !important;
        }

        #print-btn {
            display: none !important;
        }
    }
</style>
