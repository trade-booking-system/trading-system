<script>
  import Accountpicker from "./Dropdown.svelte";
  import HelloButton from "./HelloButton.svelte";
  import SumSearch from "./SumSearch.svelte";
  import TradeGrid from "./TradeGrid.svelte";
  import PositionsGrid from "./PositionsGrid.svelte";
  import WebSocketTest from "./WebSocketTest.svelte";
  import { writable } from 'svelte/store'
  import BulkBookingTabs from "./BulkBookingTabs.svelte";
  import { getContext } from "svelte";


</script>

<div class="container">
<div id="bulkBookingTabs" class = "bottomPadding">
    <BulkBookingTabs/>
  </div>
  <div class="accountpicker">
    <Accountpicker/>
  </div>
  <div id = "tradeGrid" class = "bottomPadding">
    <TradeGrid/>
  </div>
  <div id = "positionsGrid" class = "bottomPadding">
    <PositionsGrid/>
  </div>
</div>

<style>
  .container {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .accountpicker {
    margin-bottom: 10%;
  }

  .bottomPadding{
    padding-bottom: 5vh;
  }
</style>
